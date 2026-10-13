"""Cold-process contract includes imports, original loading and transmission."""
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import sys

import pytest
from scipy.sparse import csr_matrix

from ra.exact import canonical_cover
from ra.provenance import instance_hash
from ra.runner import run_request
from ra.types import CoverInstance, Request
from ra.worker import execute_request, load_instance


@pytest.fixture
def cold_request(tmp_path):
    cover = CoverInstance('', 'public-tiny', 'tiny', csr_matrix([[1, 1, 0], [0, 1, 1]]), (1, 2, 1), {'split': 'discovery'})
    identity = instance_hash(cover)
    path = tmp_path / 'input.json'
    path.write_text(json.dumps({**canonical_cover(cover), 'instance_id': identity,
                               'template_id': cover.template_id, 'cell_id': cover.cell_id, 'lineage': cover.lineage}))
    return Request(request_id='tiny', instance_path=str(path), instance_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                   instance_hash=identity, config_hash='a' * 64, code_hash='b' * 64, environment_hash='c' * 64,
                   method='native', phase='harness_validation', solver_seed=0, budget_ns=5_000_000_000,
                   watchdog_grace_ns=2_000_000_000, p0=4)


def test_normal_tiny_cold_request_includes_imports_loading_anchor_and_release(cold_request, tmp_path):
    result = run_request(cold_request, tmp_path / 'attempt')
    assert result.status == 'complete', result.error
    assert result.available.assignment_available
    assert result.available.primal_original == result.available.dual_original == 2
    assert result.available.utility == 1
    assert result.clock_aligned
    t = result.timestamps
    assert t['launch_ns'] <= t['worker_entry_ns'] <= t['imports_complete_ns'] <= t['instance_loaded_ns'] <= t['anchor_ns'] <= t['safe_return_ns'] <= t['worker_release_ns'] <= t['parent_release_ns']
    assert result.resources['worker_cpu_ns'] > 0
    assert result.resources['worker_peak_rss_bytes'] > 0
    assert result.resources['thread_environment']['OMP_NUM_THREADS'] == '1'
    assert result.resources['solver_threads'] == 1
    assert result.resources['selection_count'] == 0
    assert result.resources['selection_boundaries'] == []
    records = [json.loads(line) for line in (tmp_path / 'attempt' / 'progress.jsonl').read_text().splitlines()]
    assert records[0]['primal_original'] == 4
    assert all(r['receipt_ns'] >= r['child_ns'] for r in records)
    assignment = json.loads((tmp_path / 'attempt' / 'solutions' / (result.available.incumbent_hash + '.json')).read_text())
    assert assignment['objective'] == 2
    assert assignment['binary'] in ([1, 0, 1], [0, 1, 0])


def test_startup_outlasting_deadline_returns_no_assignment(cold_request, tmp_path):
    result = run_request(replace(cold_request, budget_ns=1), tmp_path / 'timeout')
    assert result.status == 'startup_timeout'
    assert not result.available.assignment_available
    assert result.available.utility == 0
    assert result.timestamps['parent_release_ns'] > result.timestamps['deadline_ns']
    assert result.overshoot_ns > 0


@pytest.mark.parametrize('changes', [{'method': 'learned'}, {'phase': 'confirmatory'}, {'model_path': 'fake.npz'}, {'threads': 2}, {'budget_ns': True}])
def test_unsupported_or_invalid_request_fails_explicitly(cold_request, tmp_path, changes):
    with pytest.raises(ValueError):
        run_request(replace(cold_request, **changes), tmp_path / 'unsupported')


def test_strict_original_loader_rejects_duplicate_incidence_and_file_hash(cold_request, tmp_path):
    path = Path(cold_request.instance_path)
    assert load_instance(cold_request).costs == (1, 2, 1)
    payload = json.loads(path.read_text())
    payload['rows'][0] = [0, 0]
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match='hash'):
        load_instance(cold_request)
    with pytest.raises(ValueError):
        load_instance(replace(cold_request, instance_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))


def test_fault_retains_terminal_error_and_releases_worker(cold_request, tmp_path):
    result = run_request(replace(cold_request, instance_sha256='f' * 64), tmp_path / 'bad-input')
    assert result.status == 'implementation_error'
    assert 'hash' in result.error
    assert not result.available.assignment_available
    assert result.timestamps['parent_release_ns'] >= result.timestamps['worker_release_ns']


def test_worker_module_import_is_numerically_cold():
    import subprocess
    proc = subprocess.run([sys.executable, '-c', "import sys; import ra.worker; assert not any(m in sys.modules for m in ('numpy', 'scipy', 'pyscipopt', 'sklearn'))"], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def driver(monkeypatch, tmp_path, source):
    """Real child process/SCIP, narrowly injected delay/fault at the boundary."""
    from ra import runner
    path = tmp_path / 'driver.py'
    path.write_text(source + '\nfrom pathlib import Path\nimport sys\nraise SystemExit(execute_request(Path(sys.argv[1])))\n')
    monkeypatch.setattr(runner, '_worker_argv', lambda path_arg: [sys.executable, str(path), str(path_arg)])


def test_delayed_transmission_changes_availability_with_identical_search(cold_request, tmp_path, monkeypatch):
    baseline = run_request(replace(cold_request, budget_ns=1_000_000_000), tmp_path / 'immediate')
    driver(monkeypatch, tmp_path, '''
from ra.worker import Channel, execute_request
import time
original_send, original_receive = Channel.send, Channel.receive
pending = []
deadline = None
def receive(self):
    global deadline
    packet = original_receive(self)
    if packet['kind'] == 'launch': deadline = packet['deadline_ns']
    return packet
def send(self, packet):
    if packet['kind'] == 'progress':
        pending.append(packet)
        return
    if packet['kind'] == 'terminal':
        time.sleep(max(0, (deadline - time.perf_counter_ns()) / 1e9) + .03)
        for record in pending: original_send(self, record)
    original_send(self, packet)
Channel.receive, Channel.send = receive, send
''')
    delayed = run_request(replace(cold_request, budget_ns=1_000_000_000), tmp_path / 'delayed')
    assert baseline.available.utility == 1
    assert not delayed.available.assignment_available
    assert delayed.available.utility == 0
    assert delayed.status == 'deadline'
    assert delayed.resources['native_nodes'] == baseline.resources['native_nodes']
    assert delayed.resources['native_lps'] == baseline.resources['native_lps']
    raw = [json.loads(line) for line in (tmp_path / 'delayed' / 'progress.jsonl').read_text().splitlines()]
    assert raw and all(r['child_ns'] < delayed.request.deadline_ns < r['receipt_ns'] for r in raw)


def test_actual_bad_clock_handshake_blocks_reconstruction(cold_request, tmp_path, monkeypatch):
    driver(monkeypatch, tmp_path, '''
from ra.worker import Channel, execute_request
original = Channel.send
def send(self, packet):
    if packet['kind'] == 'pong': packet['child_ns'] += 10**15
    original(self, packet)
Channel.send = send
''')
    result = run_request(cold_request, tmp_path / 'bad-clock')
    assert not result.clock_aligned
    assert result.status == 'implementation_error'
    assert 'clock' in result.error
    assert not result.available.assignment_available


@pytest.mark.parametrize('alarm', [False, True])
def test_callback_failure_retains_parent_anchor_and_correct_status(cold_request, tmp_path, monkeypatch, alarm):
    driver(monkeypatch, tmp_path, '''
from ra.worker import THREAD_SETTINGS, execute_request
import os
os.environ.update(THREAD_SETTINGS)
from ra.observer import Observer, NumericalAlarm
def fail(self, *args):
    raise ERROR('injected observation failure')
Observer.poll = fail
'''.replace('raise ERROR', 'raise NumericalAlarm' if alarm else 'raise RuntimeError'))
    result = run_request(cold_request, tmp_path / f'fault-{alarm}')
    assert result.status == ('numerical_alarm' if alarm else 'implementation_error')
    assert result.available.assignment_available
    assert result.available.primal_original == 4
    assert result.available.utility == 0
    assert result.timestamps['stop_request_ns'] <= result.timestamps['safe_return_ns'] <= result.timestamps['worker_release_ns']
    assert result.resources['native_released']
    assert result.resources['subscriptions_after_free'] == 0
    assert result.error


def test_watchdog_kills_stalled_worker_and_charges_release(cold_request, tmp_path, monkeypatch):
    driver(monkeypatch, tmp_path, '''
from ra.worker import Channel, execute_request
import time
original = Channel.send
def send(self, packet):
    if packet['kind'] == 'ready':
        original(self, packet)
        time.sleep(60)
    else: original(self, packet)
Channel.send = send
''')
    result = run_request(replace(cold_request, budget_ns=500_000_000, watchdog_grace_ns=100_000_000), tmp_path / 'watchdog')
    assert result.duration_censored
    assert result.status == 'deadline'
    assert result.available.assignment_available
    assert result.available.primal_original == 4
    assert result.timestamps['watchdog_ns'] <= result.timestamps['parent_release_ns']
    assert result.overshoot_ns >= 100_000_000
    assert result.resources['returncode'] < 0
    assert result.resources['termination']['origin'] == 'parent_watchdog'
    assert result.resources['termination']['kind'] == 'watchdog'


def test_nonzero_child_exit_cannot_be_complete(cold_request, tmp_path, monkeypatch):
    driver(monkeypatch, tmp_path, '''
from ra.worker import execute_request as real_execute
def execute_request(path):
    real_execute(path)
    return 7
''')
    result = run_request(cold_request, tmp_path / 'bad-exit')
    assert result.status == 'implementation_error'
    assert result.available.utility == 1
    assert result.resources['returncode'] == 7


def test_watchdog_covers_process_cleanup_after_channel_close(cold_request, tmp_path, monkeypatch):
    driver(monkeypatch, tmp_path, '''
from ra.worker import execute_request as real_execute
import time
def execute_request(path):
    result = real_execute(path)
    time.sleep(.8)
    return result
''')
    result = run_request(replace(cold_request, budget_ns=500_000_000, watchdog_grace_ns=100_000_000), tmp_path / 'cleanup-stall')
    assert result.duration_censored
    assert result.status == 'deadline'
    assert result.resources['returncode'] < 0
    assert result.resources['termination']['origin'] == 'parent_watchdog'
    assert result.resources['termination']['kind'] == 'watchdog'


def test_thread_environment_is_fixed_independently_of_caller(cold_request, tmp_path, monkeypatch):
    from ra.worker import THREAD_SETTINGS
    for key in THREAD_SETTINGS:
        monkeypatch.setenv(key, '7')
    result = run_request(cold_request, tmp_path / 'thread-isolation')
    assert result.status == 'complete'
    assert result.resources['thread_environment'] == THREAD_SETTINGS
    assert all(pool['num_threads'] == 1 for pool in result.resources['threadpools'])
    import os
    assert all(os.environ[key] == '7' for key in THREAD_SETTINGS)


def test_duplicate_worker_progress_is_rejected_after_valid_anchor(cold_request, tmp_path, monkeypatch):
    driver(monkeypatch, tmp_path, '''
from ra.worker import Channel, execute_request
original = Channel.send
sent = False
def send(self, packet):
    global sent
    original(self, packet)
    if packet['kind'] == 'progress' and not sent:
        sent = True
        original(self, packet)
Channel.send = send
''')
    result = run_request(cold_request, tmp_path / 'duplicate')
    assert result.status == 'implementation_error'
    assert 'duplicate' in result.error
    assert result.available.primal_original == 4


def test_resource_markers_include_anchor_observation_and_process_cpu(cold_request, tmp_path):
    result = run_request(cold_request, tmp_path / 'markers')
    t = result.timestamps
    assert t['anchor_validation_start_ns'] <= t['anchor_validation_end_ns'] <= t['anchor_submission_end_ns'] <= t['anchor_emission_start_ns'] <= t['anchor_emission_end_ns'] <= t['solve_start_ns']
    assert result.resources['worker_cpu_ns'] >= result.resources['worker_cpu_since_entry_ns'] > 0
    assert result.resources['native_overshoot_ns'] == 0
    assert result.resources['timing_partition_complete'] is False


def test_corrupt_assignment_identity_cannot_escape_solution_directory(cold_request, tmp_path, monkeypatch):
    driver(monkeypatch, tmp_path, '''
from ra.worker import Channel, execute_request
original = Channel.send
def send(self, packet):
    if packet['kind'] == 'progress':
        packet['record']['incumbent_hash'] = '../../escaped'
        if packet['assignment'] is not None: packet['assignment']['content_hash'] = '../../escaped'
    original(self, packet)
Channel.send = send
''')
    result = run_request(cold_request, tmp_path / 'bad-hash')
    assert result.status == 'implementation_error'
    assert not (tmp_path / 'escaped.json').exists()
    assert not result.available.assignment_available


def test_native_time_limit_is_deadline_even_if_safe_return_precedes_parent_deadline(cold_request, tmp_path, monkeypatch):
    driver(monkeypatch, tmp_path, '''
from ra.worker import THREAD_SETTINGS, execute_request
import os
os.environ.update(THREAD_SETTINGS)
from ra.scip_backend import ScipBackend
original = ScipBackend.optimize
def optimize(self):
    self.model.setRealParam('limits/time', 0.)
    original(self)
ScipBackend.optimize = optimize
''')
    result = run_request(cold_request, tmp_path / 'native-time-limit')
    assert result.resources['native_status'] == 'timelimit'
    assert result.timestamps['safe_return_ns'] < result.request.deadline_ns
    assert result.status == 'deadline'
    assert result.available.assignment_available


def test_failed_process_launch_retains_charged_timing(cold_request, tmp_path, monkeypatch):
    from ra import runner
    monkeypatch.setattr(runner, '_worker_argv', lambda path: [str(tmp_path / 'missing-executable'), str(path)])
    result = run_request(cold_request, tmp_path / 'failed-launch')
    assert result.status == 'implementation_error'
    assert result.request.launch_ns == result.timestamps['launch_ns']
    assert result.timestamps['launch_ns'] <= result.timestamps['parent_release_ns']
    assert result.request.deadline_ns == result.request.launch_ns + cold_request.budget_ns
    assert not result.available.assignment_available
    assert 'FileNotFoundError' in result.error
    assert result.resources['returncode'] is None
    assert 'launched_ns' not in result.timestamps
    assert 'worker_cpu_ns' not in result.resources and 'worker_peak_rss_bytes' not in result.resources
    assert result.resources['parent_cpu_ns'] > 0


def test_parent_interrupt_is_distinct_and_reaps_the_child(cold_request, tmp_path, monkeypatch):
    from ra import runner
    driver(monkeypatch, tmp_path, '''
from ra.worker import Channel, execute_request
import time
original = Channel.send
def send(self, packet):
    original(self, packet)
    if packet['kind'] == 'ready': time.sleep(1)
Channel.send = send
''')
    accepted = False
    original_accept = runner.ProgressStream.accept
    original_select = runner.select.select
    def accept(self, record):
        nonlocal accepted
        result = original_accept(self, record)
        accepted = True
        return result
    def interrupted(*args):
        if accepted:
            raise KeyboardInterrupt('injected parent interrupt after anchor')
        return original_select(*args)
    monkeypatch.setattr(runner.ProgressStream, 'accept', accept)
    monkeypatch.setattr(runner.select, 'select', interrupted)
    result = run_request(cold_request, tmp_path / 'parent-interrupt')
    assert result.available.assignment_available
    assert result.available.primal_original == 4
    assert result.available.utility == 0
    assert result.status == 'external_interrupt'
    assert result.timestamps['parent_release_ns'] >= result.timestamps['launch_ns']
    assert result.resources['returncode'] is not None
    assert result.resources['termination']['origin'] == 'parent_interrupt'
    assert result.duration_censored


@pytest.mark.parametrize('fault_site', ['observer', 'cleanup', 'structured_memory_subclass'])
def test_callback_oom_retains_category_provenance_and_received_assignment(cold_request, tmp_path, monkeypatch, fault_site):
    source = '''
from ra.worker import THREAD_SETTINGS, execute_request
import os
os.environ.update(THREAD_SETTINGS)
from ra.observer import Observer
from ra.scip_backend import _ProgressEvents, _contain_callback
'''
    if fault_site == 'cleanup':
        source += '''
original = _ProgressEvents.eventexit
@_contain_callback
def eventexit(self):
    original(self)
    raise MemoryError('injected cleanup allocation failure')
_ProgressEvents.eventexit = eventexit
'''
    else:
        source += '''
class AllocationFailure(MemoryError):
    def __init__(self, amount, detail):
        super().__init__(f'{amount}: {detail}')
def fail(self, *args):
    raise ERROR
Observer.poll = fail
'''.replace('raise ERROR', "raise AllocationFailure(17, 'injected allocation failure')" if fault_site == 'structured_memory_subclass'
            else "raise MemoryError('injected allocation failure')")
    driver(monkeypatch, tmp_path, source)
    result = run_request(cold_request, tmp_path / f'oom-{fault_site}')
    assert result.status == 'oom'
    assert result.available.assignment_available
    assert result.available.primal_original == (2 if fault_site == 'cleanup' else 4)
    assert result.available.utility == (1 if fault_site == 'cleanup' else 0)
    fault = result.resources['callback_fault']
    assert fault['status'] == 'oom'
    assert fault['exception_type'] == ('AllocationFailure' if fault_site == 'structured_memory_subclass' else 'MemoryError')
    assert result.error.startswith('CallbackError:' if fault_site == 'structured_memory_subclass' else 'MemoryError:')
    assert result.resources['native_released']
    assert result.resources['subscriptions_after_free'] == 0
    assert result.timestamps['stop_request_ns'] <= result.timestamps['worker_release_ns'] <= result.timestamps['parent_release_ns']


@pytest.mark.parametrize('signal_name,expected_status,kind', [
    ('SIGTERM', 'external_interrupt', 'termination_signal'),
    ('SIGINT', 'external_interrupt', 'termination_signal'),
    ('SIGHUP', 'external_interrupt', 'termination_signal'),
    ('SIGQUIT', 'external_interrupt', 'termination_signal'),
    ('SIGKILL', 'implementation_error', 'ambiguous_signal'),
    ('SIGABRT', 'implementation_error', 'crash_signal'),
])
@pytest.mark.parametrize('boundary', ['ready', 'terminal'])
def test_child_signal_exit_keeps_provenance_and_eligible_prefix(cold_request, tmp_path, monkeypatch, signal_name, expected_status, kind, boundary):
    import signal
    driver(monkeypatch, tmp_path, '''
from ra.worker import Channel, execute_request
import os, resource, signal
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
termination_signal = getattr(signal, SIGNAL_NAME)
if termination_signal != signal.SIGKILL:
    signal.signal(termination_signal, signal.SIG_DFL)
original = Channel.send
def send(self, packet):
    original(self, packet)
    if packet['kind'] == BOUNDARY:
        os.kill(os.getpid(), termination_signal)
Channel.send = send
'''.replace('SIGNAL_NAME', repr(signal_name)).replace('BOUNDARY', repr(boundary)))
    result = run_request(cold_request, tmp_path / f'signal-{signal_name}-{boundary}')
    assert result.status == expected_status
    assert result.status != 'oom'
    assert result.available.assignment_available
    assert result.available.primal_original == (4 if boundary == 'ready' else 2)
    assert result.available.utility == (0 if boundary == 'ready' else 1)
    assert result.resources['returncode'] == -int(getattr(signal, signal_name))
    evidence = result.resources['termination']
    assert evidence['signal_number'] == int(getattr(signal, signal_name))
    assert evidence['signal_name'] == signal_name
    assert evidence['origin'] == 'unattributed'
    assert evidence['kind'] == kind
    assert signal_name in result.error
    assert result.duration_censored
    if boundary == 'terminal':
        assert result.resources['worker_terminal_status'] == 'complete'
    else:
        assert 'worker_cpu_ns' not in result.resources and 'worker_peak_rss_bytes' not in result.resources
    assert result.timestamps['parent_release_ns'] >= result.timestamps[f'{boundary}_receipt_ns']
