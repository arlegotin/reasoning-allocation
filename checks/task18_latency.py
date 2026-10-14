"""Finite prospective public latency diagnostic; never a protected execution path."""
from dataclasses import asdict
import fcntl
import hashlib
import json
from pathlib import Path
import resource
import sys
import tempfile
import time

from ra.runner import _atomic_json, prepare_schedule, run_request

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT/'protocol/task18-latency.json'
OUT = ROOT/'artifacts/task18/latency'


def read(path):
    return json.loads(Path(path).read_text())


def stop_reason(attempt, elapsed_ns, protocol):
    if attempt.status not in ('complete', 'deadline') or attempt.quarantined:
        return 'fault_or_quarantine'
    if not attempt.resources.get('resource_release_confirmed') or attempt.resources.get('timing_instrumentation_failed'):
        return 'release_or_timing_failure'
    if attempt.overshoot_ns > protocol['stop']['overshoot_fraction'] * attempt.request.budget_ns:
        return 'overshoot_threshold'
    if elapsed_ns >= protocol['stop']['elapsed_ns']:
        return 'elapsed_cap'
    return None


def execute():
    started, cpu = time.perf_counter_ns(), time.process_time_ns()
    protocol = read(PROTOCOL)
    with (Path(tempfile.gettempdir())/'ra-primary-timed.lock').open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        # Gate before any solve or output: exact prospective source, inputs and order.
        for name, expected in protocol['files_sha256'].items():
            if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != expected:
                raise ValueError(f'prospective file changed: {name}')
        requests, metadata = prepare_schedule(ROOT/'configs/robustness.json', 'validation')
        if metadata != protocol['schedule'] or [asdict(r) for r in requests] != protocol['requests']:
            raise ValueError('prospective schedule/source/environment changed')
        OUT.mkdir(parents=True, exist_ok=False)
        _atomic_json(OUT/'protocol-receipt.json', {'path':str(PROTOCOL),
            'sha256':hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(), 'schedule':metadata}, immutable=True)
        stop = None
        completed = []
        for index, request in enumerate(requests):
            call_start = time.perf_counter_ns()
            attempt = run_request(request, OUT/'attempts'/request.request_id)
            call_end = time.perf_counter_ns()
            completed.append(attempt.attempt_id)
            stop = stop_reason(attempt, call_end-started, protocol)
            _atomic_json(OUT/f'call-{index:02d}.json', {'request_id':request.request_id,
                'attempt_id':attempt.attempt_id,'call_start_ns':call_start,'call_end_ns':call_end,
                'stop_reason':stop}, immutable=True)
            print(index+1, request.method, attempt.status, attempt.available.utility, flush=True)
            if stop:
                break
        status = {'requested':len(requests),'completed':len(completed),'attempt_ids':completed,
                  'stop_reason':stop,'completed_finite_protocol':stop is None and len(completed)==len(requests)}
        _atomic_json(OUT/'status.json', status, immutable=True)
        end = time.perf_counter_ns()
        _atomic_json(OUT/'accounting.json', {'elapsed_ns':end-started,
            'coordinator_cpu_ns':time.process_time_ns()-cpu,
            'coordinator_peak_rss_bytes':int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*(1 if sys.platform=='darwin' else 1024),
            'scope':'entry through exact identity audit, serial cold attempts, full publication and status write; final accounting write excluded',
            'coordinator_cpu_overlaps_worker':True}, immutable=True)
        _atomic_json(OUT/'reporting.json', {'accounting_write_ns':time.perf_counter_ns()-end}, immutable=True)
        return status


if __name__ == '__main__':
    print(json.dumps(execute(), sort_keys=True))
