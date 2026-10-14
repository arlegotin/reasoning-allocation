"""Single cold request. Standard-library imports only until threads are fixed.

The parent owns the transport descriptor and launch/deadline envelope. This module
is an internal process entry point, not the future general scientific run CLI.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import select
import socket
import sys
import time

from ra.types import Request
from ra.ledger import TimeLedger

THREAD_SETTINGS = {name: '1' for name in (
    'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS',
    'VECLIB_MAXIMUM_THREADS', 'NUMEXPR_NUM_THREADS', 'BLIS_NUM_THREADS')}


def strict_json(raw: str):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f'duplicate JSON key: {key}')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError(f'nonfinite JSON: {value}')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def validate_request(request: Request, *, launched: bool = False) -> None:
    if request.schema_version != 1 or type(request.schema_version) is not int:
        raise ValueError('unsupported request schema')
    if request.method not in ('native', 'depth') or request.phase not in ('harness_validation', 'discovery'):
        raise ValueError('unsupported method/phase; no learned or protected execution is implemented')
    if request.model_path is not None or request.model_hash is not None:
        raise ValueError('model loading is not implemented')
    if type(request.threads) is not int or request.threads != 1:
        raise ValueError('cold primary requests require one thread')
    if not isinstance(request.request_id, str) or not request.request_id:
        raise ValueError('request identity required')
    if not isinstance(request.instance_path, str) or not Path(request.instance_path).is_absolute():
        raise ValueError('resolved absolute input path required')
    for name in ('instance_sha256', 'instance_hash', 'config_hash', 'code_hash', 'environment_hash'):
        value = getattr(request, name)
        if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError(f'invalid resolved {name}')
    for name in ('budget_ns', 'watchdog_grace_ns', 'p0'):
        if type(getattr(request, name)) is not int or getattr(request, name) <= 0:
            raise ValueError(f'{name} must be a positive integer')
    if type(request.solver_seed) is not int or not 0 <= request.solver_seed <= 2147483647:
        raise ValueError('invalid SCIP solver seed')
    for name in ('integrality_tolerance', 'bound_tolerance'):
        value = getattr(request, name)
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value < .5:
            raise ValueError(f'invalid {name}')
    if launched:
        if (type(request.launch_ns) is not int or request.launch_ns < 0
                or type(request.deadline_ns) is not int
                or request.deadline_ns != request.launch_ns + request.budget_ns):
            raise ValueError('invalid launch/deadline envelope')
    elif request.launch_ns is not None or request.deadline_ns is not None:
        raise ValueError('launch/deadline are parent-owned runtime fields')


def load_instance(request: Request):
    """Strict canonical original JSON loader, called inside the charged child."""
    raw = Path(request.instance_path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != request.instance_sha256:
        raise ValueError('instance file hash mismatch')
    payload = strict_json(raw.decode())
    if not isinstance(payload, dict) or set(payload) != {'shape', 'rows', 'costs', 'instance_id', 'template_id', 'cell_id', 'lineage'}:
        raise ValueError('invalid original instance schema')
    shape, rows, costs = payload['shape'], payload['rows'], payload['costs']
    if (not isinstance(shape, list) or len(shape) != 2
            or any(type(v) is not int or v <= 0 for v in shape)
            or not isinstance(rows, list) or len(rows) != shape[0]
            or not isinstance(costs, list) or len(costs) != shape[1]
            or any(type(c) is not int or c <= 0 for c in costs)):
        raise ValueError('invalid original dimensions/costs')
    indices, offsets = [], [0]
    for row in rows:
        if (not isinstance(row, list) or not row
                or any(type(j) is not int or not 0 <= j < shape[1] for j in row)
                or row != sorted(set(row))):
            raise ValueError('original rows must be sorted unique binary incidences')
        indices.extend(row)
        offsets.append(len(indices))
    if any(not isinstance(payload[name], str) or not payload[name] for name in ('instance_id', 'template_id', 'cell_id')):
        raise ValueError('invalid instance identities')
    if not isinstance(payload['lineage'], dict):
        raise ValueError('invalid lineage')
    from scipy.sparse import csr_matrix
    from ra.exact import canonical_cover
    from ra.provenance import instance_hash
    from ra.types import CoverInstance
    incidence = csr_matrix(([1] * len(indices), indices, offsets), shape=tuple(shape))
    instance = CoverInstance(payload['instance_id'], payload['template_id'], payload['cell_id'], incidence,
                             tuple(costs), payload['lineage'])
    canonical_cover(instance)
    if instance.instance_id != request.instance_hash or instance_hash(instance) != request.instance_hash:
        raise ValueError('canonical instance hash mismatch')
    if sum(instance.costs) != request.p0:
        raise ValueError('anchor objective differs from resolved p0')
    return instance


class Channel:
    """Local duplex framed pipe. Wrappers here own no native solver state."""
    def __init__(self, connection: socket.socket):
        self.connection = connection
        self.buffer = b''

    def send(self, payload):
        self.connection.sendall((json.dumps(payload, separators=(',', ':'), allow_nan=False) + '\n').encode())

    def receive(self):
        while b'\n' not in self.buffer:
            chunk = self.connection.recv(65536)
            if not chunk:
                raise EOFError('parent/worker channel closed')
            self.buffer += chunk
        line, self.buffer = self.buffer.split(b'\n', 1)
        return strict_json(line.decode())

    def stop_pending(self):
        if b'\n' in self.buffer or select.select([self.connection], [], [], 0)[0]:
            packet = self.receive()
            if packet != {'kind': 'stop'}:
                raise ValueError('unexpected parent message during solve')
            return True
        return False


class StartupTimeout(Exception):
    pass


def _failure_status(exc: BaseException) -> str:
    """Primitive callback category survives safe reconstruction and cleanup."""
    callback_status = getattr(exc, 'callback_fault', {}).get('status')
    if type(exc).__name__ == 'NumericalAlarm' or callback_status == 'numerical_alarm':
        return 'numerical_alarm'
    if isinstance(exc, MemoryError) or callback_status == 'oom':
        return 'oom'
    if isinstance(exc, KeyboardInterrupt):
        return 'external_interrupt'
    return 'implementation_error'


def execute_request(request_path: Path) -> int:
    entry = time.perf_counter_ns()
    cpu_start = time.process_time_ns()
    channel = Channel(socket.socket(fileno=int(os.environ['RA_CHANNEL_FD'])))
    ledger = TimeLedger(entry)
    ledger.enter('startup', entry)
    timestamps = {'worker_entry_ns': entry}
    resources = {}
    backend = model = observer = None
    status, error, exit_code = 'implementation_error', None, 1
    try:
        request = Request(**strict_json(Path(request_path).read_text()))
        validate_request(request)
        launch = channel.receive()
        if set(launch) != {'kind', 'launch_ns', 'deadline_ns'} or launch['kind'] != 'launch':
            raise ValueError('missing parent launch envelope')
        request = replace(request, launch_ns=launch['launch_ns'], deadline_ns=launch['deadline_ns'])
        validate_request(request, launched=True)
        for _ in range(3):
            ping = channel.receive()
            if ping['kind'] != 'ping':
                raise ValueError('clock ping expected')
            channel.send({'kind': 'pong', 'parent_send_ns': ping['parent_send_ns'], 'child_ns': time.perf_counter_ns()})
        alignment = channel.receive()
        if alignment != {'kind': 'aligned', 'ok': True}:
            raise ValueError('clock alignment failed; reconstruction blocked')

        def startup_check():
            if time.perf_counter_ns() >= request.deadline_ns:
                timestamps.setdefault('stop_request_ns', time.perf_counter_ns())
                raise StartupTimeout()

        startup_check()
        os.environ.update(THREAD_SETTINGS)
        timestamps['threads_fixed_ns'] = time.perf_counter_ns()
        from pyscipopt import Model, quicksum
        from threadpoolctl import threadpool_info, threadpool_limits
        from ra.exact import canonical_cover
        from ra.observer import Observer, NumericalAlarm
        from ra.scip_backend import ScipBackend
        # Import SciPy under fixed settings even before first original input load.
        import scipy.sparse
        timestamps['imports_complete_ns'] = time.perf_counter_ns()
        startup_check()
        with threadpool_limits(limits=1):
            instance = load_instance(request)
            timestamps['instance_loaded_ns'] = time.perf_counter_ns()
            resources['instance'] = {'instance_id': instance.instance_id, 'template_id': instance.template_id,
                                     'cell_id': instance.cell_id, 'lineage': instance.lineage}
            resources['thread_environment'] = {k: os.environ[k] for k in THREAD_SETTINGS}
            resources['threadpools'] = threadpool_info()
            resources['input_bytes'] = Path(request.instance_path).stat().st_size
            resources['model_bytes'] = 0
            startup_check()
            model = Model('ra-cold-cover')
            model.hideOutput()
            model.setIntParam('parallel/maxnthreads', request.threads)
            model.setIntParam('lp/threads', request.threads)
            model.setIntParam('randomization/randomseedshift', request.solver_seed)
            model.setRealParam('numerics/feastol', request.integrality_tolerance)
            variables = [model.addVar(name=f'x{i}', vtype='B', obj=c) for i, c in enumerate(instance.costs)]
            rows = canonical_cover(instance)['rows']
            for row in rows:
                model.addCons(quicksum(variables[j] for j in row) >= 1)
            observer = Observer(instance, request_id=request.request_id,
                                integrality_tolerance=request.integrality_tolerance, bound_tolerance=request.bound_tolerance)
            backend = ScipBackend(model, costs=instance.costs, rows=rows, observer=observer,
                                  install_selector=request.method == 'depth', deadline_ns=request.deadline_ns,
                                  stop_poll=channel.stop_pending)
            observer.time_ledger = backend.time_ledger = ledger
            ledger.enter('observation', time.perf_counter_ns())
            timestamps['anchor_validation_start_ns'] = time.perf_counter_ns()
            anchor = observer.validate_incumbent((1,) * len(instance.costs), time.perf_counter_ns())
            timestamps['anchor_validation_end_ns'] = time.perf_counter_ns()
            ledger.leave(time.perf_counter_ns())
            timestamps['anchor_submission_start_ns'] = time.perf_counter_ns()
            sol = model.createSol()
            for variable in variables:
                model.setSolVal(sol, variable, 1)
            accepted = model.addSol(sol, free=True)
            del sol, variables
            timestamps['anchor_submission_end_ns'] = time.perf_counter_ns()
            if not accepted:
                raise NumericalAlarm('native solver rejected verified anchor')
            startup_check()
            published = set()

            def publish(record):
                assignment = None
                if record.incumbent_hash is not None and record.incumbent_hash not in published:
                    assignment = asdict(observer.assignments[record.incumbent_hash])
                channel.send({'kind': 'progress', 'record': asdict(record), 'assignment': assignment})
                published.add(record.incumbent_hash)

            observer.publish = publish
            ledger.enter('observation', time.perf_counter_ns())
            timestamps['anchor_emission_start_ns'] = time.perf_counter_ns()
            publish(anchor)
            timestamps['anchor_emission_end_ns'] = time.perf_counter_ns()
            ledger.leave(time.perf_counter_ns())
            timestamps['anchor_ns'] = time.perf_counter_ns()
            timestamps['startup_complete_ns'] = time.perf_counter_ns()
            channel.send({'kind': 'ready', 'child_ns': timestamps['startup_complete_ns']})
            remaining = max(0., (request.deadline_ns - time.perf_counter_ns()) / 1e9)
            model.setRealParam('limits/time', remaining)
            timestamps['solve_start_ns'] = time.perf_counter_ns()
            ledger.enter('native', time.perf_counter_ns())
            try:
                backend.optimize()
            finally:
                ledger.leave(time.perf_counter_ns())
            timestamps['solve_end_ns'] = time.perf_counter_ns()
            resources['native_status'] = str(model.getStatus())
            status = ('deadline' if time.perf_counter_ns() >= request.deadline_ns or backend.stop_requested
                      or resources['native_status'] in ('timelimit', 'userinterrupt') else 'complete')
            exit_code = 0
    except StartupTimeout:
        status, exit_code = 'startup_timeout', 0
    except BaseException as exc:
        status = _failure_status(exc)
        error = f'{type(exc).__name__}: {exc}'
        resources['callback_fault'] = getattr(exc, 'callback_fault', None)
    finally:
        timestamps['finalization_start_ns'] = time.perf_counter_ns()
        ledger.enter('finalization', timestamps['finalization_start_ns'])
        if backend is not None:
            timestamps['safe_return_ns'] = backend.safe_return_ns
            resources['native_overshoot_ns'] = max(0, (backend.safe_return_ns or request.deadline_ns) - request.deadline_ns)
            resources.update({'selection_count': backend.selection_count,
                              'selection_boundaries': [asdict(b) for b in backend.selection_boundaries],
                              'lease_outcomes': [asdict(o) for o in backend.lease_controller.outcomes] if backend.lease_controller else [],
                              'progress_events': dict(backend.progress_events), 'native_events': dict(backend.events),
                              'completion_count': backend.processed_nodes,
                              'solver_threads': request.threads, 'lp_threads': request.threads})
        if model is not None:
            try:
                resources.update(native_nodes=int(model.getNTotalNodes()), native_lps=int(model.getNLPs()))
                model.freeProb()
                resources['native_released'] = True
                if backend is not None:
                    resources['subscriptions_after_free'] = backend.subscriptions + backend.progress_subscriptions
                    backend.raise_if_failed()
            except BaseException as exc:
                if error is None:
                    status = _failure_status(exc)
                    error = f'{type(exc).__name__}: {exc}'
                    resources['callback_fault'] = getattr(exc, 'callback_fault', None)
                exit_code = 1
        if backend is not None:
            # Teardown callbacks can introduce a first fault/stop during freeProb.
            timestamps['stop_request_ns'] = backend.stop_request_ns or timestamps.get('stop_request_ns')
        if observer is not None:
            resources['observation_intervals'] = observer.intervals
            resources['last_native_dual'] = observer.last_native_dual
        usage = resource.getrusage(resource.RUSAGE_SELF)
        resources['worker_cpu_ns'] = time.process_time_ns()
        resources['worker_cpu_since_entry_ns'] = resources['worker_cpu_ns'] - cpu_start
        resources['worker_cpu_scope'] = 'process start through pre-terminal cleanup; parent wait covers later release'
        resources['worker_peak_rss_bytes'] = int(usage.ru_maxrss) * (1 if sys.platform == 'darwin' else 1024)
        timestamps['worker_release_ns'] = time.perf_counter_ns()
        resources['worker_exclusive_ns'] = None if ledger.failed else ledger.summary(timestamps['worker_release_ns'])
        resources['timing_instrumentation_failed'] = ledger.failed
        resources['worker_timing_scope'] = 'worker entry through pre-terminal cleanup; interpreter tail is parent residual'
        channel.send({'kind': 'terminal', 'status': status, 'error': error,
                      'timestamps': timestamps, 'resources': resources})
        channel.connection.close()
    return exit_code


if __name__ == '__main__':
    raise SystemExit(execute_request(Path(sys.argv[1])))
