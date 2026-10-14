"""Real parent transport/recovery with a standard-library, no-solver worker."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import sys

import numpy as np
import pytest

from ra import collect, runner
from ra.config import load_feature_schema
from ra.exact import verify_cover
from ra.metrics import summarize_attempts
from ra.types import LeaseOutcome, NodeKey
from ra.worker import load_instance
from test_worker import cold_request


WORKER = '''
import json, os, signal, socket, sys, time
request = json.load(open(sys.argv[1]))
sock = socket.socket(fileno=int(os.environ['RA_CHANNEL_FD']))
reader = sock.makefile('rb')
def send(value):
    sock.sendall((json.dumps(value) + '\\n').encode())
launch = json.loads(reader.readline())
for _ in range(3):
    ping = json.loads(reader.readline())
    send(dict(kind='pong', parent_send_ns=ping['parent_send_ns'], child_ns=time.perf_counter_ns()))
assert json.loads(reader.readline())['ok']
assignment = json.loads(sys.argv[4])
send(dict(kind='progress', record=dict(request_id=request['request_id'], sequence=1,
    child_ns=time.perf_counter_ns(), receipt_ns=None, primal_original=2, dual_original=0.,
    incumbent_hash=assignment['content_hash'], assignment_available=True), assignment=assignment))
send(dict(kind='terminal', status=sys.argv[3],
    error='injected correctness alarm' if sys.argv[3]=='numerical_alarm' else None,
    timestamps={}, resources=dict(instance=dict(template_id='public-tiny', cell_id='tiny', lineage={}))))
if sys.argv[2] == 'transport':
    send(dict(kind='invalid-after-terminal'))
elif sys.argv[2] == 'signal':
    os.kill(os.getpid(), signal.SIGTERM)
'''


@pytest.mark.parametrize('terminal_status', ['numerical_alarm', 'complete'])
@pytest.mark.parametrize('failure', ['finalization', 'transport', 'interrupt', 'signal', 'publication'])
def test_observed_alarm_survives_secondary_parent_failure(
        cold_request, tmp_path, monkeypatch, terminal_status, failure):
    # Downgrading status after a terminal alarm must fail the quarantine,
    # recovery, endpoint, and real trace-label assertions below.
    _, _, _, run = collect._collection_plan(Path('configs/exploratory.json'))
    method = run['methods'][0]
    request = replace(cold_request, method=method['name'], phase='train',
        method_config={**method, 'lease_lengths': run['lease_lengths']})
    assignment = asdict(verify_cover(load_instance(cold_request), [1, 0, 1], 0.))
    script = tmp_path / 'synthetic_worker.py'
    script.write_text(WORKER)

    def argv(request_path):
        trace = request_path.parent / 'trace'
        writer = collect.TraceWriter(trace, load_feature_schema(Path('configs/features.json')), max_decisions=1)
        allocation = dict(root=dict(epoch=1, number=1), node_limit=1, selection_probability=1.,
            policy_state_hash='p', gain_prediction=None, seconds_prediction=None, seconds_q90=None)
        writer.decision(np.zeros(192), dict(allocation=allocation, pool_ids=[allocation['root']],
            pool_hash='pool', support_lengths=[1], support_hash='support', heuristic=[allocation['root'], 1]))
        runner._atomic_json(trace / 'dispatch-000000.json', dict(allocation=allocation, pool_hash='pool',
            entry_ns=0, snapshot_ns=2, dispatch_ns=5, local_utility_entry=0.), immutable=True)
        runner._atomic_json(trace / 'outcome-000000.json', asdict(LeaseOutcome(NodeKey(1, 1), 1, 1,
            0, 5, 20, 'node_limit', True, False, 0., 15, 0, 0., snapshot_ns=2, trace_index=0)), immutable=True)
        return [sys.executable, str(script), str(request_path), failure, terminal_status, json.dumps(assignment)]

    monkeypatch.setattr(runner, '_worker_argv', argv)
    processes = []
    spawn = runner.subprocess.Popen

    def spawn_worker(*args, **kwargs):
        process = spawn(*args, **kwargs)
        processes.append(process)
        return process

    monkeypatch.setattr(runner.subprocess, 'Popen', spawn_worker)
    checkpoints = []
    atomic_json = runner._atomic_json
    interrupted = False

    def checkpoint(path, payload, **kwargs):
        nonlocal interrupted
        atomic_json(path, payload, **kwargs)
        if path.name == 'partial.json':
            checkpoints.append(json.loads(path.read_text()))
            if failure == 'interrupt' and 'terminal_receipt_ns' in payload['timestamps'] and not interrupted:
                interrupted = True
                # Exercise interruption after release deterministically; an
                # alive worker would also set censored during termination.
                processes[0].wait(timeout=2)
                raise KeyboardInterrupt('injected parent interruption')

    monkeypatch.setattr(runner, '_atomic_json', checkpoint)
    if failure == 'finalization':
        def fail_finalization(*args, **kwargs):
            raise ValueError('injected trace finalization failure')
        monkeypatch.setattr(collect, 'finalize_trace', fail_finalization)
    if failure == 'publication':
        def fail_publication(*args):
            raise KeyboardInterrupt('injected publication interruption')
        monkeypatch.setattr(runner, 'publish_attempt', fail_publication)

    out = tmp_path / 'attempts' / 'one'
    if failure == 'publication':
        with pytest.raises(KeyboardInterrupt, match='publication'):
            runner.run_request(request, out)
    else:
        result = runner.run_request(request, out)
        assert result.resources['resource_release_confirmed']
        protocol = dict(deadlines_ns=[request.budget_ns], weights=[1.], fit_ids=['f'],
            physical_methods={'A': {'name': request.method}}, planning={'native_methods': [], 'cells': {'tiny': 1.}})
        row, = summarize_attempts([result], protocol)
        assert row['correctness_alarm'] is (terminal_status == 'numerical_alarm')
        assert row['utility'] == .5

    payload, final = runner._read_attempt(out)
    assert final is (failure != 'publication')
    assert payload['available']['utility'] == .5
    if failure in ('interrupt', 'signal', 'publication'):
        assert payload['duration_censored']
    if terminal_status == 'numerical_alarm':
        assert payload['quarantined'] and payload['status'] == 'numerical_alarm'
        assert 'injected correctness alarm' in payload['error']
        observed = [p for p in checkpoints if 'terminal_receipt_ns' in p['timestamps']]
        assert observed and all(p['quarantined'] for p in observed)
        assert all(p['resources']['correctness_alarm']['error'] == 'injected correctness alarm' for p in observed)
        with pytest.raises(ValueError, match='configuration quarantined'):
            runner.resume_requests([replace(request, request_id='another')], out.parent)
    else:
        assert not payload['quarantined'] and payload['status'] != 'numerical_alarm'
        assert 'correctness_alarm' not in payload['resources']
        pending = runner.resume_requests([request], out.parent)
        assert bool(pending) is (failure in ('interrupt', 'signal', 'publication'))
    if failure != 'publication':
        detail = {'finalization': 'injected trace finalization failure', 'transport': 'invalid-after-terminal',
                  'interrupt': 'injected parent interruption', 'signal': 'SIGTERM'}[failure]
        assert detail in payload['error']
    if failure != 'finalization':
        label = json.loads((out / 'trace' / 'label-000000.json').read_text())
        eligible = terminal_status != 'numerical_alarm'
        assert label['body_fit_eligible'] is eligible
        assert label['gain_fit_eligible'] is eligible
        assert label['duration_observation_known'] is eligible
        if failure in ('interrupt', 'signal'):
            assert label['attempt_duration_censored']
