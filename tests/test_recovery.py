"""Durable attempts are immutable; failures and partial costs survive resume."""
from dataclasses import asdict, replace
import hashlib
from pathlib import Path
import json

import pytest

from ra import runner
from ra.runner import run_request
from test_worker import cold_request, driver


def test_atomic_manifest_and_artifact_hashes_are_verified(cold_request, tmp_path):
    root = tmp_path / 'runs'
    attempt = run_request(cold_request, root / 'one')
    assert runner.resume_requests([cold_request], root) == []
    assert attempt.attempt_id
    with pytest.raises(FileExistsError):
        runner.publish_attempt(attempt, root / 'one')
    (root / 'one' / 'progress.jsonl').write_text('corrupt\n')
    with pytest.raises(ValueError, match='hash'):
        runner.resume_requests([cold_request], root)


@pytest.mark.parametrize('field', ['code_hash', 'model_hash', 'build_hash', 'config_hash', 'environment_hash', 'instance_sha256'])
def test_resume_rejects_changed_hashes(cold_request, tmp_path, field):
    run_request(cold_request, tmp_path / 'one')
    with pytest.raises(ValueError, match='hash'):
        runner.resume_requests([replace(cold_request, **{field: 'f' * 64})], tmp_path)


def test_interrupted_publication_preserves_partial_and_prior_costs(cold_request, tmp_path, monkeypatch):
    publish = runner.publish_attempt
    def interrupted(*args):
        raise KeyboardInterrupt('during atomic finalization')
    monkeypatch.setattr(runner, 'publish_attempt', interrupted)
    with pytest.raises(KeyboardInterrupt):
        run_request(cold_request, tmp_path / 'one')
    partial = json.loads((tmp_path / 'one' / 'partial.json').read_text())
    assert partial['available']['utility'] == 1
    assert not (tmp_path / 'one' / 'attempt.json').exists()
    pending, = runner.resume_requests([cold_request], tmp_path)
    assert pending.prior_attempt_ids == (partial['attempt_id'],)
    assert pending.prior_costs['end_to_end_ns'] > 0
    monkeypatch.setattr(runner, 'publish_attempt', publish)
    rerun = run_request(pending, tmp_path / 'two')
    assert rerun.attempt_id != partial['attempt_id']
    assert rerun.prior_attempt_id == partial['attempt_id']
    assert rerun.cumulative_prior_costs == pending.prior_costs
    assert runner.resume_requests([cold_request], tmp_path) == []


@pytest.mark.parametrize('boundary', ['load', 'progress', 'lease', 'finalization'])
def test_interruption_at_charged_boundaries_preserves_outcomes(cold_request, tmp_path, monkeypatch, boundary):
    source = '''
from ra.worker import THREAD_SETTINGS, execute_request
import os
os.environ.update(THREAD_SETTINGS)
'''
    source += {
        'load': '''
import ra.worker as worker
original = worker.load_instance
def load(request):
    original(request)
    raise KeyboardInterrupt('after original model loading')
worker.load_instance = load
''',
        'progress': '''
from ra.worker import Channel
original = Channel.send
def send(self, packet):
    original(self, packet)
    if packet['kind'] == 'ready': raise KeyboardInterrupt('after published progress')
Channel.send = send
''',
        'lease': LEASE_INTERRUPT_DRIVER,
        'finalization': '''
from ra.worker import Channel
original = Channel.send
def send(self, packet):
    if packet['kind'] == 'terminal':
        import signal
        os.kill(os.getpid(), signal.SIGTERM)
    original(self, packet)
Channel.send = send
''',
    }[boundary]
    if boundary == 'lease':
        cold_request = branching_request(cold_request, tmp_path)
    driver(monkeypatch, tmp_path, source)
    result = run_request(cold_request, tmp_path / 'one')
    assert result.status == 'external_interrupt'
    assert result.resources['end_to_end_ns'] > 0
    assert result.resources['resource_release_confirmed']
    if boundary != 'load':
        assert result.available.assignment_available
    if boundary == 'lease':
        outcomes = result.resources['lease_outcomes']
        assert sum(o['work'] for o in outcomes) > 0
        assert all(o['work'] + o['unused_units'] == o['node_limit'] for o in outcomes)
    pending, = runner.resume_requests([cold_request], tmp_path)
    assert pending.prior_attempt_ids == (result.attempt_id,)
    assert pending.prior_costs['end_to_end_ns'] == result.resources['end_to_end_ns']


@pytest.mark.parametrize('fault,status', [('MemoryError', 'oom'), ('RuntimeError', 'implementation_error'), ('NumericalAlarm', 'numerical_alarm')])
def test_fault_is_costed_outcome_and_correctness_alarm_quarantines(cold_request, tmp_path, monkeypatch, fault, status):
    driver(monkeypatch, tmp_path, '''
from ra.worker import THREAD_SETTINGS, execute_request
import os
os.environ.update(THREAD_SETTINGS)
from ra.observer import Observer, NumericalAlarm
def fail(*args): raise FAULT('injected failure')
Observer.poll = fail
'''.replace('FAULT', fault))
    result = run_request(cold_request, tmp_path / 'one')
    assert result.status == status
    assert result.available.primal_original == 4
    assert result.resources['end_to_end_ns'] > 0
    if status == 'numerical_alarm':
        assert result.quarantined
        with pytest.raises(ValueError, match='quarantin'):
            runner.resume_requests([replace(cold_request, request_id='other')], tmp_path)
    else:
        assert runner.resume_requests([cold_request], tmp_path) == []


def test_watchdog_retains_lower_bounds_and_overshoot(cold_request, tmp_path, monkeypatch):
    driver(monkeypatch, tmp_path, '''
from ra.worker import Channel, execute_request
import time
original = Channel.send
def send(self, packet):
    original(self, packet)
    if packet['kind'] == 'ready': time.sleep(60)
Channel.send = send
''')
    result = run_request(replace(cold_request, budget_ns=500_000_000, watchdog_grace_ns=100_000_000), tmp_path / 'one')
    assert result.duration_censored
    assert result.resources['duration_lower_bound_ns'] >= 600_000_000
    assert result.resources['worker_sampled_cpu_ns_lower_bound'] > 0
    assert result.overshoot_ns >= 100_000_000
    assert result.available.primal_original == 4
    assert result.resources['worker_exclusive_ns'] is None
    assert not result.resources['timing_partition_complete']


def test_torn_manifest_commit_is_resumable_without_overwrite(cold_request, tmp_path, monkeypatch):
    original = runner.os.link
    def fail_manifest(source, target):
        if target.name == 'attempt.json':
            raise KeyboardInterrupt('between digest and manifest commit')
        original(source, target)
    monkeypatch.setattr(runner.os, 'link', fail_manifest)
    with pytest.raises(KeyboardInterrupt):
        run_request(cold_request, tmp_path / 'one')
    assert (tmp_path / 'one' / 'attempt.sha256').exists()
    assert not (tmp_path / 'one' / 'attempt.json').exists()
    pending, = runner.resume_requests([cold_request], tmp_path)
    assert pending.prior_costs['attempt_count'] == 1
    assert pending.prior_costs['end_to_end_ns'] > 0


def test_partial_reconstructs_durable_progress_newer_than_checkpoint(cold_request, tmp_path, monkeypatch):
    original = runner._atomic_json
    def fail_after_progress(path, payload, **kwargs):
        if path.name == 'partial.json' and payload['available']['assignment_available']:
            raise KeyboardInterrupt('checkpoint interruption')
        original(path, payload, **kwargs)
    monkeypatch.setattr(runner, '_atomic_json', fail_after_progress)
    with pytest.raises(KeyboardInterrupt):
        run_request(cold_request, tmp_path / 'one')
    partial, final = runner._read_attempt(tmp_path / 'one')
    assert not final
    assert partial['available']['assignment_available']
    assert partial['available']['primal_original'] == 4
    assert partial['duration_censored']
    assert partial['resources']['trace_bytes'] > 0


def test_resume_refuses_still_running_attempt(cold_request, tmp_path):
    import fcntl
    directory = tmp_path / 'one'
    directory.mkdir()
    (directory / 'request.json').write_text(json.dumps(asdict(cold_request)))
    with (directory / 'active.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match='running'):
            runner.resume_requests([cold_request], tmp_path)


def test_outer_publication_accounting_includes_receipt_write(cold_request, tmp_path, monkeypatch):
    import time
    original = runner._atomic_json
    def delayed_receipt(path, value, **kwargs):
        if path.name == 'publication.json': time.sleep(.02)
        original(path, value, **kwargs)
    monkeypatch.setattr(runner, '_atomic_json', delayed_receipt)
    attempt = run_request(cold_request, tmp_path / 'one')
    cost = json.loads((tmp_path / 'one' / 'accounting.json').read_text())
    receipt = json.loads((tmp_path / 'one' / 'publication.json').read_text())
    assert cost['publish_call_ns'] >= receipt['publication_ns'] + 20_000_000
    assert cost['total_observed_ns'] == cost['collection_end_ns'] - attempt.timestamps['launch_ns']
    assert cost['total_observed_ns'] == attempt.resources['end_to_end_ns'] + cost['publication_ns']
    assert cost['audit_write_tail_ns'] is None


def test_missing_publication_tail_remains_explicitly_unknown(cold_request, tmp_path, monkeypatch):
    original = runner._atomic_json
    def interrupt_receipt(path, payload, **kwargs):
        if path.name == 'publication.json': raise KeyboardInterrupt('receipt crash')
        original(path, payload, **kwargs)
    monkeypatch.setattr(runner, '_atomic_json', interrupt_receipt)
    with pytest.raises(KeyboardInterrupt):
        run_request(cold_request, tmp_path / 'one')
    payload, final = runner._read_attempt(tmp_path / 'one')
    assert final
    cost = runner._prior_costs([payload])
    assert cost['unknown_publication_attempts'] == 1
    assert runner.resume_requests([cold_request], tmp_path) == []


LEASE_INTERRUPT_DRIVER = """
from ra.scip_backend import ScipBackend
from ra.leases import LeaseController
from ra.types import Allocation
from pyscipopt import SCIP_PARAMSETTING as P
original_init = ScipBackend.__init__
original_event = ScipBackend._on_event
def init(self, model, **kwargs):
    original_init(self, model, **kwargs)
    model.setPresolve(P.OFF)
    model.setHeuristics(P.OFF)
    model.setSeparating(P.OFF)
    model.setIntParam('presolving/maxrestarts', -1)
    self.lease_controller = LeaseController(self.parents, deadline_ns=self.deadline_ns, request_stop=self.request_stop)
    def choose(records):
        root = min(records, key=lambda n: (-n.depth, n.key.number)).key
        self.lease_controller.begin(Allocation(root, 8, 0., 0., None, None, 'diagnostic'), self.last_callback_entry_ns)
        return root
    self.choose = choose
def event(self, native_event):
    original_event(self, native_event)
    lease = self.lease_controller
    if lease.ledger is not None and lease.ledger.snapshot()['spent']:
        raise KeyboardInterrupt('injected interruption after real lease completion')
ScipBackend.__init__, ScipBackend._on_event = init, event
"""


def branching_request(request, directory):
    from scipy.sparse import csr_matrix
    from ra.scip_backend import _case_definition
    from ra.types import CoverInstance
    from ra.provenance import instance_hash
    from ra.exact import canonical_cover
    fixture = _case_definition('branching')
    rows, cols = zip(*((i, j) for i, row in enumerate(fixture['rows']) for j in row))
    cover = CoverInstance('', 'public-branching', 'diagnostic',
        csr_matrix(([1] * len(rows), (rows, cols)), shape=(len(fixture['rows']), len(fixture['costs']))),
        tuple(fixture['costs']), {'split': 'discovery'})
    identity = instance_hash(cover)
    path = directory / 'branching.json'
    path.write_text(json.dumps({**canonical_cover(cover), 'instance_id': identity,
        'template_id': cover.template_id, 'cell_id': cover.cell_id, 'lineage': cover.lineage}))
    return replace(request, method='depth', instance_path=str(path), p0=sum(cover.costs),
        instance_hash=identity, instance_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def test_partial_solution_content_must_match_original_hash(cold_request, tmp_path, monkeypatch):
    monkeypatch.setattr(runner, 'publish_attempt', lambda *args: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        run_request(cold_request, tmp_path / 'one')
    for path in (tmp_path / 'one' / 'solutions').glob('*.json'):
        value = json.loads(path.read_text())
        value['binary'] = [0, 0, 0]
        path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match='assignment'):
        runner.resume_requests([cold_request], tmp_path)



def test_prior_costs_retain_counts_peaks_and_unknowns_without_summing_rss():
    prior = [
        {'resources': {'end_to_end_ns': 10, 'worker_cpu_ns': 4, 'worker_peak_rss_bytes': 100,
                       'native_nodes': 3, 'native_lps': 2, 'parent_sampling_ns': 1, 'trace_bytes': 20}},
        {'resources': {'end_to_end_ns': 20, 'worker_sampled_cpu_ns_lower_bound': 5,
                       'worker_sampled_peak_rss_bytes': 80, 'parent_sampling_ns': 2, 'trace_bytes': 30}},
    ]
    cost = runner._prior_costs(prior)
    assert cost['worker_peak_rss_bytes_lower_bound'] == 100
    assert cost['native_nodes'] == 3 and cost['native_lps'] == 2
    assert cost['unavailable_counts']['native_nodes'] == 1
    assert cost['parent_sampling_ns'] == 3
    assert cost['trace_bytes'] == 50
    assert cost['worker_cpu_ns_lower_bound'] == 9


@pytest.mark.parametrize('boundary', ['request.json', 'partial.json'])
def test_first_partial_interruption_is_recoverable_without_worker_launch(cold_request, tmp_path, monkeypatch, boundary):
    original = runner._atomic_json
    def interrupt_initial_partial(path, value, **kwargs):
        if path.name == boundary:
            raise KeyboardInterrupt('bootstrap publication boundary')
        original(path, value, **kwargs)
    def forbidden_launch(*args, **kwargs):
        pytest.fail('bootstrap interruption must precede worker launch')
    monkeypatch.setattr(runner, '_atomic_json', interrupt_initial_partial)
    monkeypatch.setattr(runner.subprocess, 'Popen', forbidden_launch)
    with pytest.raises(KeyboardInterrupt):
        run_request(cold_request, tmp_path / 'one')
    pending, = runner.resume_requests([cold_request], tmp_path)
    assert len(pending.prior_attempt_ids) == 1
    saved, final = runner._read_attempt(tmp_path / 'one')
    assert not final and saved['attempt_id'] == pending.prior_attempt_ids[0]
    assert not saved['available']['assignment_available']
    assert 'worker_cpu_ns' not in saved['resources']
    assert saved['resources']['bootstrap_costs_unavailable']
    assert pending.prior_costs['initialization_ns'] == saved['resources']['initialization_ns']
    assert runner.resume_requests([cold_request], tmp_path)[0].prior_attempt_ids == pending.prior_attempt_ids


@pytest.mark.parametrize('loaded', [True, False])
def test_manifest_stores_validated_instance_provenance(cold_request, tmp_path, loaded):
    request = cold_request if loaded else replace(cold_request, budget_ns=1)
    attempt = run_request(request, tmp_path / 'one')
    manifest = json.loads((tmp_path / 'one' / 'attempt.json').read_text())
    assert manifest['template_id'] == ('public-tiny' if loaded else None)
    assert manifest['cell_id'] == ('tiny' if loaded else None)
    assert manifest['lineage'] == ({'split': 'discovery'} if loaded else None)
    assert manifest['instance_provenance_available'] is loaded
    assert attempt.instance_provenance_available is loaded
