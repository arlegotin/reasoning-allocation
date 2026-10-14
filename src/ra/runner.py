"""Cold single-request parent with authoritative complete-frame receipt times.

Immutable attempt publication/recovery and serial public control schedules.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import json
import hashlib
import fcntl
from uuid import uuid4
from typing import Sequence

import psutil
import os
from pathlib import Path
import select
import signal
import socket
import subprocess
import sys
import time

from ra.metrics import ProgressStream, progress_at, validate_clock_alignment
from ra.types import AttemptStatus, Attempt, AvailableProgress, ProgressRecord, Request
from ra.worker import Channel, strict_json, validate_request


def _worker_argv(request_path: Path) -> list[str]:
    return [sys.executable, '-m', 'ra.worker', str(request_path)]


def _signal_evidence(returncode: int, parent_termination: str | None) -> dict[str, object]:
    """Keep signal identity without inventing its sender or an OOM diagnosis."""
    number = -returncode
    try:
        name = signal.Signals(number).name
    except ValueError:
        name = f'SIGNAL_{number}'
    if parent_termination is not None:
        kind = 'watchdog' if parent_termination == 'parent_watchdog' else parent_termination
    elif number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT):
        kind = 'termination_signal'
    elif number in (signal.SIGABRT, signal.SIGSEGV, signal.SIGILL, signal.SIGFPE, signal.SIGBUS):
        kind = 'crash_signal'
    else:
        # SIGKILL can be requested by a user, an OS OOM killer, or another cause.
        kind = 'ambiguous_signal'
    return {'signal_number': number, 'signal_name': name,
            'origin': parent_termination or 'unattributed', 'kind': kind}


def run_request(request: Request, out: Path) -> Attempt:
    validate_request(request)
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    with (out / 'active.lock').open('xb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _run_request(request, out)


def _run_request(request: Request, out: Path) -> Attempt:
    bootstrap_start, bootstrap_cpu = time.perf_counter_ns(), time.process_time_ns()
    (out / 'solutions').mkdir()
    attempt_id = uuid4().hex
    # Publish identity before request discovery or any process/socket allocation.
    # This immutable lower-bound checkpoint survives a failed first partial write.
    _atomic_json(out / 'bootstrap.json', {'schema_version': 1, 'attempt_id': attempt_id,
        'request_id': request.request_id, 'request': asdict(request),
        'timestamps': {'bootstrap_ns': bootstrap_start},
        'resources': {'end_to_end_ns': 0, 'parent_cpu_ns': time.process_time_ns() - bootstrap_cpu,
                      'initialization_ns': time.perf_counter_ns() - bootstrap_start,
                      'bootstrap_costs_unavailable': True, 'resource_release_confirmed': False},
        'available': asdict(AvailableProgress(False, 0., None, 0., None)),
        'clock_aligned': False, 'duration_censored': True, 'quarantined': False,
        'template_id': None, 'cell_id': None, 'lineage': None, 'instance_provenance_available': False}, immutable=True)
    request_path = out / 'request.json'
    _atomic_json(request_path, asdict(request))
    argv = _worker_argv(request_path)
    records, samples = [], []
    timestamps = {}
    resources = {'clock_samples': samples, 'resource_scope': 'one worker; overlapping parent cost separate',
                 'timing_partition_complete': False, 'argv': argv,
                 'timer_resolution_ns': max(1, round(time.get_clock_info('perf_counter').resolution * 1e9)),
                 'parent_sampling_ns': 0}
    terminal = None
    stream = None
    aligned = False
    ready = False
    error = None
    parent_failure = False
    parent_interrupted = False
    parent_termination = None
    censored = False
    stop_sent = False
    parent_cpu = time.process_time_ns()
    resources['initialization_cpu_ns'] = parent_cpu - bootstrap_cpu
    resources['initialization_ns'] = time.perf_counter_ns() - bootstrap_start
    observation_ns = 0
    buffer = b''
    process = None
    pending_ping = None
    monitor = None
    last_sample = 0

    def checkpoint():
        now = time.perf_counter_ns()
        resources['end_to_end_ns'] = now - timestamps.get('launch_ns', now)
        resources['parent_cpu_ns'] = time.process_time_ns() - parent_cpu
        resources['parent_observation_ns_overlapping_worker'] = observation_ns
        resources['trace_bytes'] = sum((out / name).stat().st_size for name in
            ('wire.jsonl', 'progress.jsonl', 'stdout.log', 'stderr.log') if (out / name).exists())
        available = (progress_at(records, request.deadline_ns, request.p0, bound_tolerance=request.bound_tolerance)
                     if aligned and records else AvailableProgress(False, 0., None, 0., None))
        _atomic_json(out / 'partial.json', {'schema_version': 1, 'attempt_id': attempt_id,
                     'request_id': request.request_id, 'request': asdict(request),
                     'timestamps': {**timestamps, 'checkpoint_ns': now}, 'resources': resources,
                     'available': asdict(available), 'clock_aligned': aligned,
                     'template_id': resources.get('instance', {}).get('template_id'),
                     'cell_id': resources.get('instance', {}).get('cell_id'),
                     'lineage': resources.get('instance', {}).get('lineage'),
                     'instance_provenance_available': 'instance' in resources,
                     'duration_censored': True, 'quarantined': terminal is not None and terminal['status'] == 'numerical_alarm'})

    def sample():
        nonlocal last_sample
        started = time.perf_counter_ns()
        if monitor is not None:
            try:
                with monitor.oneshot():
                    cpu = monitor.cpu_times()
                    rss = monitor.memory_info().rss
                resources['worker_sampled_cpu_ns_lower_bound'] = max(resources.get('worker_sampled_cpu_ns_lower_bound', 0), round((cpu.user + cpu.system) * 1e9))
                resources['worker_sampled_peak_rss_bytes'] = max(resources.get('worker_sampled_peak_rss_bytes', 0), rss)
                resources['worker_last_sample_ns'] = time.perf_counter_ns()
            except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                resources['sampling_unavailable'] = type(exc).__name__
        resources['parent_sampling_ns'] += time.perf_counter_ns() - started
        last_sample = started

    checkpoint()
    parent, child = socket.socketpair()
    env = os.environ.copy()
    env['RA_CHANNEL_FD'] = str(child.fileno())
    channel = Channel(parent)
    with (out / 'stdout.log').open('wb') as stdout, (out / 'stderr.log').open('wb') as stderr, \
            (out / 'wire.jsonl').open('w') as wire, (out / 'progress.jsonl').open('w') as progress_file:
        try:
            launch_ns = time.perf_counter_ns()
            resources['initialization_ns'] = launch_ns - bootstrap_start
            request = replace(request, launch_ns=launch_ns, deadline_ns=launch_ns + request.budget_ns)
            timestamps.update(launch_ns=launch_ns, deadline_ns=request.deadline_ns)
            checkpoint()
            process = subprocess.Popen(argv, env=env, pass_fds=(child.fileno(),), stdout=stdout, stderr=stderr)
            timestamps['launched_ns'] = time.perf_counter_ns()
            monitor = psutil.Process(process.pid)
            sample()
            child.close()
            channel.send({'kind': 'launch', 'launch_ns': launch_ns, 'deadline_ns': request.deadline_ns})

            def ping():
                nonlocal pending_ping
                pending_ping = time.perf_counter_ns()
                channel.send({'kind': 'ping', 'parent_send_ns': pending_ping})

            ping()
            eof = False
            while not eof:
                now = time.perf_counter_ns()
                if now - last_sample >= 50_000_000:
                    sample()
                    checkpoint()
                # Finish bootstrap first: the child checks the absolute deadline
                # before imports. A stop frame cannot be mistaken for a clock ping.
                if aligned and now >= request.deadline_ns and not stop_sent:
                    timestamps['parent_stop_request_ns'] = now
                    try:
                        channel.send({'kind': 'stop'})
                    except OSError as exc:
                        # macOS may report ENOTCONN when the worker closes just
                        # before this advisory send. Drain queued terminal data.
                        import errno
                        if exc.errno not in (errno.EPIPE, errno.ECONNRESET, errno.ENOTCONN):
                            raise
                        resources['parent_stop_send'] = {'delivered': False, 'socket_send_returned': False, 'errno': exc.errno,
                            'scope': 'advisory stop send failed after peer close; terminal drain continues'}
                    else:
                        resources['parent_stop_send'] = {'delivered': None, 'socket_send_returned': True, 'errno': None,
                            'scope': 'socket send returned; worker processing is not acknowledged'}
                    stop_sent = True
                if now >= request.deadline_ns + request.watchdog_grace_ns and process.poll() is None:
                    timestamps['watchdog_ns'] = now
                    parent_termination = 'parent_watchdog'
                    process.terminate()
                    censored = True
                    try:
                        process.wait(timeout=.25)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    timestamps['parent_release_ns'] = time.perf_counter_ns()
                remaining = max(0., (request.deadline_ns + request.watchdog_grace_ns - now) / 1e9)
                if not select.select([parent], [], [], min(.05, remaining) if remaining else .01)[0]:
                    if process.poll() is not None:
                        # Exit closes the child's socket; the next read drains its buffered frames.
                        continue
                    continue
                started = time.perf_counter_ns()
                try:
                    chunk = parent.recv(65536)
                except ConnectionResetError:
                    chunk = b''
                if not chunk:
                    eof = True
                    if buffer:
                        raise ValueError('truncated worker frame')
                    continue
                buffer += chunk
                while b'\n' in buffer:
                    line, buffer = buffer.split(b'\n', 1)
                    packet = strict_json(line.decode())
                    receipt = time.perf_counter_ns()
                    wire.write(json.dumps({'receipt_ns': receipt, 'packet': packet}, allow_nan=False) + '\n')
                    wire.flush()
                    kind = packet['kind']
                    if kind == 'pong':
                        if len(samples) >= 3 or packet['parent_send_ns'] != pending_ping:
                            raise ValueError('duplicate/out-of-order clock response')
                        samples.append((pending_ping, packet['child_ns'], receipt))
                        if len(samples) < 3:
                            ping()
                        else:
                            aligned = validate_clock_alignment(samples)
                            channel.send({'kind': 'aligned', 'ok': aligned})
                            checkpoint()
                            if not aligned:
                                error = 'clock alignment failed; label reconstruction blocked'
                    elif kind == 'ready':
                        ready = True
                        timestamps['ready_receipt_ns'] = receipt
                    elif kind == 'progress':
                        if terminal is not None:
                            raise ValueError('progress after terminal record')
                        record = ProgressRecord(**packet['record'])
                        if record.receipt_ns is not None or record.request_id != request.request_id:
                            raise ValueError('worker cannot set receipt time or change request identity')
                        record = replace(record, receipt_ns=receipt)
                        if stream is None:
                            stream = ProgressStream(request.deadline_ns, request.p0, clock_aligned=aligned,
                                                    bound_tolerance=request.bound_tolerance)
                        stream.accept(record)
                        assignment = packet['assignment']
                        identity = record.incumbent_hash
                        if identity is not None and (not isinstance(identity, str) or len(identity) != 64
                                or any(c not in '0123456789abcdef' for c in identity)):
                            raise ValueError('invalid content-addressed assignment hash')
                        path = out / 'solutions' / f'{record.incumbent_hash}.json'
                        if assignment is not None:
                            if (assignment['content_hash'] != record.incumbent_hash
                                    or assignment['objective'] != record.primal_original
                                    or any(type(v) is not int or v not in (0, 1) for v in assignment['binary'])):
                                raise ValueError('invalid published assignment identity')
                            if not path.exists():
                                _atomic_json(path, assignment, immutable=True)
                        elif record.assignment_available and not path.exists():
                            raise ValueError('published assignment array missing')
                        records.append(record)
                        progress_file.write(json.dumps(asdict(record), allow_nan=False) + '\n')
                        progress_file.flush()
                        os.fsync(progress_file.fileno())
                        checkpoint()
                    elif kind == 'terminal':
                        if terminal is not None:
                            raise ValueError('duplicate terminal record')
                        terminal = packet
                        timestamps.update(packet['timestamps'])
                        timestamps['terminal_receipt_ns'] = receipt
                        resources.update(packet['resources'])
                        checkpoint()
                    else:
                        raise ValueError(f'unknown worker packet: {kind}')
                observation_ns += time.perf_counter_ns() - started
            try:
                process.wait(timeout=max(0., (request.deadline_ns + request.watchdog_grace_ns - time.perf_counter_ns()) / 1e9))
            except subprocess.TimeoutExpired:
                timestamps['watchdog_ns'] = time.perf_counter_ns()
                parent_termination = 'parent_watchdog'
                process.terminate()
                censored = True
                try:
                    process.wait(timeout=.25)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            timestamps.setdefault('parent_release_ns', time.perf_counter_ns())
        except BaseException as exc:
            parent_failure = True
            parent_interrupted = isinstance(exc, KeyboardInterrupt)
            error = f'{type(exc).__name__}: {exc}'
            if process is not None and process.poll() is None:
                parent_termination = 'parent_interrupt' if parent_interrupted else 'parent_failure'
                process.terminate()
                censored = True
                try:
                    process.wait(timeout=.25)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            timestamps['parent_release_ns'] = time.perf_counter_ns()
        finally:
            child.close()
            parent.close()
    # Preserve the last valid prefix on ordinary method/transport failures.
    available = (progress_at(records, request.deadline_ns, request.p0, bound_tolerance=request.bound_tolerance)
                 if aligned else AvailableProgress(False, 0., None, 0., None))
    if terminal is not None:
        status = terminal['status']
        error = error or terminal['error']
    else:
        status = 'deadline' if censored and ready else 'startup_timeout' if censored else 'implementation_error'
        error = error or 'worker exited without terminal record'
    if parent_failure or error and terminal is not None and status in ('complete', 'deadline', 'startup_timeout'):
        status = 'implementation_error'
    if not aligned:
        status = 'implementation_error' if not censored else status
    if status == 'complete' and timestamps['parent_release_ns'] > request.deadline_ns:
        status = 'deadline'
    if process is not None and process.returncode != 0 and status in ('complete', 'deadline', 'startup_timeout') and not censored:
        status = 'implementation_error'
        error = error or f'worker exited with status {process.returncode}'
    if parent_interrupted:
        status = 'external_interrupt'
    resources['resource_release_confirmed'] = process is not None and process.returncode is not None
    resources['returncode'] = process.returncode if process is not None else None
    if terminal is not None:
        resources['worker_terminal_status'] = terminal['status']
    if process is not None and process.returncode is not None and process.returncode < 0:
        termination = _signal_evidence(process.returncode, parent_termination)
        resources['termination'] = termination
        if parent_termination is None and not parent_failure:
            status = 'external_interrupt' if termination['kind'] == 'termination_signal' else 'implementation_error'
        detail = (f"worker terminated by {termination['signal_name']} "
                  f"({termination['origin']}, {termination['kind']})")
        error = f'{error}; {detail}' if error else detail
        censored = True
    if {'collection', 'learned'} & request.method_config.keys():
        from ra.collect import finalize_trace
        try:
            resources['collection'] = finalize_trace(out, records, request, timestamps['parent_release_ns'], aligned,
                resources.get('selection_boundaries', []), status, censored,
                timing_valid=resources.get('timing_instrumentation_failed') is not True)
        except (ValueError, OSError, TypeError) as exc:
            status, error = 'implementation_error', f'collection finalization: {exc}'
    resources['parent_cpu_ns'] = time.process_time_ns() - parent_cpu
    resources['parent_observation_ns_overlapping_worker'] = observation_ns
    resources['trace_bytes'] = sum((out / name).stat().st_size for name in ('wire.jsonl', 'progress.jsonl', 'stdout.log', 'stderr.log'))
    # Finalization may fail after retaining arrays/metadata; count physical
    # evidence independently of whether a collection summary was published.
    resources['trace_bytes'] += sum(p.stat().st_size for p in (out / 'trace').rglob('*') if p.is_file())
    resources['clock_max_bracket_ns'] = max((end - start for start, _, end in samples), default=None)
    # Flush trace/log data before the final accounting boundary.
    for path in out.rglob('*'):
        if path.is_file():
            with path.open('rb') as stream_file:
                os.fsync(stream_file.fileno())
    timestamps['parent_finalize_ns'] = time.perf_counter_ns()
    end = timestamps['parent_finalize_ns']
    start = timestamps['launch_ns']
    release = timestamps['parent_release_ns']
    resources['end_to_end_ns'] = end - start
    resources['duration_lower_bound_ns'] = release - start
    worker_start, worker_end = timestamps.get('worker_entry_ns'), timestamps.get('worker_release_ns')
    totals = resources.get('worker_exclusive_ns')
    if aligned and totals is not None and start <= worker_start <= worker_end <= release:
        resources['timing_partition_complete'] = sum(totals.values()) == worker_end - worker_start
        resources['elapsed_partition_ns'] = {'parent_launch': worker_start - start,
            'worker_accounted': worker_end - worker_start, 'release_residual': release - worker_end,
            'parent_finalization': end - release}
    else:
        resources['worker_exclusive_ns'] = None
        resources['elapsed_partition_ns'] = {'launch_through_release_unclassified': release - start,
                                             'parent_finalization': end - release}
    resources['elapsed_scope'] = 'launch through flushed traces and pre-manifest finalization; publication receipt adds its measured cost'
    resources['fallback_count'] = 0
    resources['cpu_tail_unmeasured'] = True
    resources['parent_cpu_ns'] = time.process_time_ns() - parent_cpu

    finalization_cpu = time.process_time_ns()
    if status == 'complete' and end > request.deadline_ns:
        status = 'deadline'
    censored = censored or status == 'external_interrupt'
    deadline = request.deadline_ns or timestamps['parent_finalize_ns']
    provenance = resources.get('instance', {})
    attempt = Attempt(request.request_id, status, available, aligned, timestamps, resources,
                      max(0, timestamps['parent_release_ns'] - deadline), censored, error, request,
                      attempt_id=attempt_id,
                      prior_attempt_id=request.prior_attempt_ids[-1] if request.prior_attempt_ids else None,
                      cumulative_prior_costs=dict(request.prior_costs), quarantined=status == 'numerical_alarm',
                      template_id=provenance.get('template_id'), cell_id=provenance.get('cell_id'),
                      lineage=provenance.get('lineage'), instance_provenance_available=bool(provenance))
    _atomic_json(out / 'partial.json', asdict(attempt))
    publication_start = time.perf_counter_ns()
    publish_attempt(attempt, out)
    collection_end = time.perf_counter_ns()
    _atomic_json(out / 'accounting.json', {'schema_version': 1, 'attempt_id': attempt_id,
        'manifest_sha256': hashlib.sha256((out / 'attempt.json').read_bytes()).hexdigest(),
        'publication_ns': collection_end - end,
        'publish_call_ns': collection_end - publication_start,
        'parent_cpu_ns': time.process_time_ns() - finalization_cpu,
        'collection_end_ns': collection_end, 'total_observed_ns': collection_end - start,
        'audit_write_tail_ns': None,
        'scope': 'nonoverlapping continuation from manifest accounting endpoint through publish and receipt; this audit write is report-generation overhead'}, immutable=True)
    return attempt


def _json_bytes(value) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def _sync_directory(directory: Path) -> None:
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_json(path: Path, value, *, immutable=False) -> None:
    """Flush a same-directory temporary inode, then publish without truncation."""
    temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    with temporary.open('xb') as stream:
        stream.write(_json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())
    if immutable:
        os.link(temporary, path)  # Atomic create-if-absent; never overwrite an attempt.
        temporary.unlink()
    else:
        os.replace(temporary, path)
    _sync_directory(path.parent)


def publish_attempt(attempt: Attempt, directory: Path) -> Path:
    """Publish a final manifest after flushing all data; partials remain on failure.

    The digest seals the exact manifest bytes. The manifest is the commit point;
    its presence alone is insufficient unless every content hash also verifies.
    """
    publication_start = time.perf_counter_ns()
    publication_cpu = time.process_time_ns()
    directory = Path(directory)
    target = directory / 'attempt.json'
    if target.exists():
        raise FileExistsError(target)
    files = {}
    for path in sorted(directory.rglob('*')):
        if path.is_file() and path.name not in ('attempt.sha256', 'publication.json', 'accounting.json', 'partial.json', 'active.lock') and not path.name.endswith('.tmp'):
            with path.open('rb') as stream:
                os.fsync(stream.fileno())
            files[str(path.relative_to(directory))] = hashlib.sha256(path.read_bytes()).hexdigest()
    _sync_directory(directory / 'solutions') if (directory / 'solutions').exists() else None
    payload = {**asdict(attempt), 'files_sha256': files}
    _atomic_json(directory / 'attempt.sha256', {'sha256': hashlib.sha256(_json_bytes(payload)).hexdigest()}, immutable=True)
    _atomic_json(target, payload, immutable=True)
    _atomic_json(directory / 'publication.json', {'schema_version': 1, 'attempt_id': attempt.attempt_id,
        'manifest_sha256': hashlib.sha256(_json_bytes(payload)).hexdigest(),
        'publication_ns': time.perf_counter_ns() - publication_start,
        'parent_cpu_ns': time.process_time_ns() - publication_cpu,
        'scope': 'manifest flush/commit; receipt writing tail measured by outer caller'}, immutable=True)
    return target


def _request_identity(value: dict) -> dict:
    return {key: item for key, item in value.items()
            if key not in ('launch_ns', 'deadline_ns', 'prior_attempt_ids', 'prior_costs')}


def _read_attempt(directory: Path) -> tuple[dict, bool]:
    final = directory / 'attempt.json'
    if final.exists():
        raw = final.read_bytes()
        expected = strict_json((directory / 'attempt.sha256').read_text())['sha256']
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError(f'manifest hash mismatch: {final}')
        payload = strict_json(raw.decode())
        for name, digest in payload['files_sha256'].items():
            path = directory / name
            if not path.resolve().is_relative_to(directory.resolve()) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError(f'artifact hash mismatch: {path}')
        AttemptStatus(payload['status'])
        return payload, True
    checkpoint_path = directory / 'partial.json'
    if not checkpoint_path.exists():
        checkpoint_path = directory / 'bootstrap.json'
    payload = strict_json(checkpoint_path.read_text())
    # The durable progress journal may be ahead of the last atomic checkpoint.
    # Reconstruct only complete records; an unfinished last write earns no utility.
    progress_path = directory / 'progress.jsonl'
    if progress_path.exists() and payload.get('clock_aligned'):
        raw = progress_path.read_bytes()
        complete = raw[:raw.rfind(b'\n') + 1]
        records = [ProgressRecord(**strict_json(line.decode())) for line in complete.splitlines()]
        from ra.worker import load_instance
        from ra.exact import verify_cover
        instance = load_instance(Request(**payload['request'])) if records else None
        verified = {}
        for record in records:
            if record.assignment_available:
                identity = record.incumbent_hash
                if not isinstance(identity, str) or len(identity) != 64 or any(c not in '0123456789abcdef' for c in identity):
                    raise ValueError('invalid partial assignment hash')
                assignment = strict_json((directory / 'solutions' / f'{identity}.json').read_text())
                if identity not in verified:
                    try:
                        verified[identity] = verify_cover(instance, assignment['binary'], 0.)
                    except ValueError as exc:
                        raise ValueError(f'invalid partial assignment: {exc}') from None
                checked = verified[identity]
                if (checked.content_hash != identity or assignment['content_hash'] != identity
                        or checked.objective != record.primal_original or assignment['objective'] != record.primal_original):
                    raise ValueError('partial assignment hash mismatch')
        request = payload['request']
        if records:
            resources = payload['resources']
            resources['end_to_end_ns'] = max(resources.get('end_to_end_ns', 0), records[-1].receipt_ns - request['launch_ns'])
        payload['available'] = asdict(progress_at(records, request['deadline_ns'], request['p0'],
                                                 bound_tolerance=request['bound_tolerance']))
    payload['resources']['trace_bytes'] = sum((directory / name).stat().st_size for name in
        ('wire.jsonl', 'progress.jsonl', 'stdout.log', 'stderr.log') if (directory / name).exists())
    payload['resources']['trace_bytes'] += sum(p.stat().st_size for p in (directory / 'trace').rglob('*') if p.is_file())
    payload['duration_censored'] = True
    return payload, False


def _prior_costs(attempts: list[dict]) -> dict[str, object]:
    """Sum each physical attempt once, never its already cumulative totals."""
    result = {'attempt_count': len(attempts), 'end_to_end_ns': 0, 'parent_cpu_ns': 0,
              'worker_cpu_ns_lower_bound': 0, 'unknown_worker_cpu_attempts': 0,
              'trace_bytes': 0, 'duration_censored_attempts': 0,
              'publication_ns': 0, 'unknown_publication_attempts': 0}
    additive = ('initialization_ns', 'initialization_cpu_ns', 'native_nodes', 'native_lps', 'model_bytes', 'input_bytes',
                'parent_sampling_ns', 'parent_observation_ns_overlapping_worker', 'fallback_count')
    result.update(dict.fromkeys(additive, 0))
    result['unavailable_counts'] = dict.fromkeys(additive, 0)
    result['worker_peak_rss_bytes_lower_bound'] = None
    result['unknown_worker_rss_attempts'] = 0
    for attempt in attempts:
        resources = attempt['resources']
        result['unknown_publication_attempts'] += not resources.get('publication_accounting_complete', False)
        for name in additive:
            if name in resources:
                result[name] += resources[name]
            else:
                result['unavailable_counts'][name] += 1
        peaks = [resources[name] for name in ('worker_peak_rss_bytes', 'worker_sampled_peak_rss_bytes') if name in resources]
        if peaks:
            result['worker_peak_rss_bytes_lower_bound'] = max(result['worker_peak_rss_bytes_lower_bound'] or 0, *peaks)
        else:
            result['unknown_worker_rss_attempts'] += 1
        for name in ('end_to_end_ns', 'parent_cpu_ns', 'trace_bytes', 'publication_ns'):
            result[name] += resources.get(name, 0)
        observed = [resources[name] for name in ('worker_cpu_ns', 'worker_sampled_cpu_ns_lower_bound') if name in resources]
        cpu = max(observed) if observed else None
        if cpu is None:
            result['unknown_worker_cpu_attempts'] += 1
        else:
            result['worker_cpu_ns_lower_bound'] += cpu
        result['duration_censored_attempts'] += bool(attempt.get('duration_censored', True))
    result['total_observed_ns'] = result['end_to_end_ns'] + result['publication_ns']
    return result


def resume_requests(requests: Sequence[Request], root: Path) -> list[Request]:
    """Schedule missing/interrupted requests only; never erase fault outcomes.

    Partial attempts preserve lower bounds, not invented finished durations.
    Correctness alarms quarantine the configuration even across request IDs.
    """
    by_request = {}
    quarantined = set()
    ids = set()
    directories = {p.parent for name in ('request.json', 'bootstrap.json') for p in Path(root).rglob(name)}
    for directory in sorted(directories):
        lock_path = directory / 'active.lock'
        if lock_path.exists():
            with lock_path.open('rb') as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise ValueError(f'attempt still running: {directory}') from None
                payload, final = _read_attempt(directory)
        else:
            payload, final = _read_attempt(directory)
        identity = payload['attempt_id']
        if identity in ids:
            raise ValueError('duplicate immutable attempt ID')
        ids.add(identity)
        if payload.get('quarantined') or payload.get('status') == 'numerical_alarm':
            quarantined.add(payload['request']['config_hash'])
        receipt = directory / 'accounting.json'
        if not receipt.exists():
            receipt = directory / 'publication.json'
        if receipt.exists():
            publication = strict_json(receipt.read_text())
            if publication['attempt_id'] != identity:
                raise ValueError('publication identity mismatch')
            if not final or publication['manifest_sha256'] != hashlib.sha256((directory / 'attempt.json').read_bytes()).hexdigest():
                raise ValueError('publication manifest hash mismatch')
            payload['resources']['publication_accounting_complete'] = receipt.name == 'accounting.json'
            payload['resources']['publication_ns'] = publication['publication_ns']
            payload['resources']['parent_cpu_ns'] += publication['parent_cpu_ns']
        by_request.setdefault(payload['request_id'], []).append((payload, final))
    pending = []
    seen = set()
    for request in requests:
        if request.request_id in seen:
            raise ValueError('duplicate request ID')
        seen.add(request.request_id)
        prior = by_request.get(request.request_id, [])
        identity = _request_identity(asdict(request))
        if any(_request_identity(item['request']) != identity for item, _ in prior):
            raise ValueError(f'request/hash mismatch for {request.request_id}')
        if request.config_hash in quarantined:
            raise ValueError(f'configuration quarantined: {request.config_hash}')
        if any(final and item['status'] != 'external_interrupt' for item, final in prior):
            continue
        prior.sort(key=lambda pair: (pair[0]['timestamps'].get('launch_ns', 0), pair[0]['attempt_id']))
        pending.append(replace(request, prior_attempt_ids=tuple(item['attempt_id'] for item, _ in prior),
                               prior_costs=_prior_costs([item for item, _ in prior])))
    return pending


def _digest(value) -> str:
    return hashlib.sha256(_json_bytes(value)).hexdigest()


def _runtime_identity() -> tuple[str, str, str, dict]:
    """Exact source/dependency/build identity without raw hardware identifiers."""
    import platform
    from importlib import metadata
    import pyscipopt
    sources = {str(p.relative_to(Path(__file__).parent)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in sorted(Path(__file__).parent.rglob('*.py'))}
    binary = Path(pyscipopt.scip.__file__)
    # Hash the extension plus the linked wheel's native SCIP library.
    libraries = [binary, *sorted(binary.parent.parent.glob('pyscipopt.libs/*')),
                 *sorted(binary.parent.glob('.dylibs/*'))]
    build = {str(p.name): hashlib.sha256(p.read_bytes()).hexdigest() for p in libraries if p.is_file()}
    packages = {d.metadata['Name']: d.version for d in metadata.distributions()}
    environment = {'python': sys.version, 'executable': sys.executable, 'machine': platform.machine(),
                   'platform': platform.platform(), 'packages': packages, 'build': build}
    return _digest(sources), _digest(environment), _digest(build), {'sources': sources, 'environment': environment}


def prepare_schedule(config_path: Path, phase: str) -> tuple[list[Request], dict]:
    """Validate public ownership and resolve a deterministic serial request list."""
    from ra.config import load_config
    from ra.provenance import SplitOwnership
    from ra.worker import load_instance
    import random
    if phase not in ('discovery','pilot','train','validation'):
        raise ValueError('protected/confirmatory execution unavailable until freeze')
    config_path = Path(config_path).resolve()
    config = load_config(config_path, 'run')
    code_hash, environment_hash, build_hash, inventory = _runtime_identity()
    config_hash = _digest(config)
    allowed = {'discovery'} if phase in ('discovery','pilot') else {phase}
    requests = []
    manifest_hashes = {}
    seen_inputs = set()
    seen_instances = set()
    ownership = SplitOwnership()
    for manifest_name in config['input_manifests']:
        manifest_path = Path(manifest_name)
        if not manifest_path.is_absolute(): manifest_path = config_path.parent / manifest_path
        manifest_path = manifest_path.resolve()
        raw = manifest_path.read_bytes()
        manifest_hashes[str(manifest_path)] = hashlib.sha256(raw).hexdigest()
        manifest = strict_json(raw.decode())
        if not isinstance(manifest,dict) or manifest.get('split') not in allowed or not isinstance(manifest.get('instances'),list) or not manifest['instances'] or not isinstance(manifest.get('ownership_registry'),str) or not manifest['ownership_registry']:
            raise ValueError('manifest must contain configured public phase inputs')
        registry_path = Path(manifest['ownership_registry'])
        if not registry_path.is_absolute():
            registry_path = registry_path.resolve() if registry_path.exists() else manifest_path.parent / registry_path
        manifest_hashes[str(registry_path.resolve())] = hashlib.sha256(registry_path.read_bytes()).hexdigest()
        owners = SplitOwnership.load(registry_path)
        for item in manifest['instances']:
            if (not isinstance(item,dict) or not {'path','sha256','instance_id'} <= item.keys()
                    or any(not isinstance(item[k],str) or not item[k] for k in ('path','sha256','instance_id'))):
                raise ValueError('invalid input manifest record')
            input_path = (manifest_path.parent / item['path']).resolve()
            if not input_path.is_relative_to(manifest_path.parent) or input_path in seen_inputs:
                raise ValueError('input path escapes namespace or is duplicated')
            seen_inputs.add(input_path)
            payload = strict_json(input_path.read_text())
            if not isinstance(payload,dict) or not isinstance(payload.get('lineage'),dict) or not isinstance(payload.get('costs'),list) or any(type(c) is not int or c <= 0 for c in payload['costs']):
                raise ValueError('invalid original input metadata/costs')
            if 'split' in payload['lineage'] and payload['lineage']['split'] != manifest['split']:
                raise ValueError('input lineage/manifest split mismatch')
            provisional = Request('validation', str(input_path), item['sha256'], item['instance_id'], config_hash,
                code_hash, environment_hash, 'native', manifest['split'], 0, 1, 1, sum(payload['costs']))
            instance = load_instance(provisional)
            if instance.instance_id in seen_instances:
                raise ValueError('duplicate original instance identity across input paths')
            seen_instances.add(instance.instance_id)
            local = SplitOwnership(); local.register(instance,manifest['split'])
            if any(owners.owners.get(key) != split for key,split in local.owners.items()):
                raise ValueError('input is not registered in declared public namespace')
            ownership.register(instance,manifest['split'])
            for seed in config['solver_seeds']:
                for budget in config['budgets_ns']:
                    block=[]
                    for method in config['methods']:
                        identity = [phase, instance.instance_id, method['name'], seed, budget]
                        block.append(replace(provisional, request_id=_digest(identity), method=method['name'],
                            phase=phase, solver_seed=seed, budget_ns=budget, watchdog_grace_ns=config['watchdog_grace_ns'],
                            integrality_tolerance=config['integrality_tolerance'], bound_tolerance=config['bound_tolerance'],
                            build_hash=build_hash, method_config={**method,'lease_lengths':config['lease_lengths']},
                            model_path=method.get('allocator',{}).get('model_path'),
                            model_hash=method.get('allocator',{}).get('model_hash')))
                    order_seed = int(_digest([config['run_order_seed'],phase,instance.instance_id,seed,budget]),16)
                    random.Random(order_seed).shuffle(block)
                    requests.extend(block)
    if len({request.request_id for request in requests}) != len(requests):
        raise ValueError('duplicate scheduled request identity')
    metadata = {'schema_version':1, 'config':config, 'config_path':str(config_path), 'config_hash':config_hash,
                'phase':phase, 'input_manifest_sha256':manifest_hashes, 'inventory':inventory,
                'request_order':[r.request_id for r in requests], 'serial':True, 'threads':1}
    return requests, metadata


def run_schedule(config_path: Path, phase: str, out: Path, *, resume: bool = False,
                 dry_run: bool = False) -> list[Attempt]:
    """Cold serial requests, immutable per-attempt output and batch accounting.

    Batch elapsed includes request bootstrap, audit writes, release and publication.
    Coordinator CPU overlaps child CPU and is reported separately, never summed as wall time.
    """
    if dry_run:
        prepare_schedule(config_path, phase)
        return []
    import tempfile
    # Admit before imports, native models, hashes or sparse input preparation.
    with (Path(tempfile.gettempdir())/'ra-primary-timed.lock').open('a+b') as timed_lock:
        try: fcntl.flock(timed_lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('another primary timed run is active') from None
        return _run_schedule(config_path, phase, out, resume=resume)


def _run_schedule(config_path: Path, phase: str, out: Path, *, resume: bool) -> list[Attempt]:
    batch_start, batch_cpu = time.perf_counter_ns(), time.process_time_ns()
    requests, metadata = prepare_schedule(config_path, phase)
    out = Path(out).resolve()
    if out.exists() and any(out.iterdir()) and not resume:
        raise ValueError('nonempty run output requires --resume')
    out.mkdir(parents=True,exist_ok=True)
    # Serialize coordinators as well as workers; a second timed run cannot overlap.
    import resource
    with (out/'schedule.lock').open('a+b') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError: raise ValueError('schedule already active') from None
        schedule_path = out/'schedule.json'
        if schedule_path.exists():
            if strict_json(schedule_path.read_text()) != metadata:
                raise ValueError('schedule identity/hash mismatch on resume')
        else: _atomic_json(schedule_path,metadata,immutable=True)
        pending = resume_requests(requests,out) if resume else requests
        batch = out/('batch-'+uuid4().hex); batch.mkdir()
        _atomic_json(batch/'request-order.json',[asdict(r) for r in pending],immutable=True)
        attempts=[]
        for request in pending:
            call_start = time.perf_counter_ns()
            attempt = run_request(request,out/'attempts'/request.request_id/uuid4().hex)
            call_end = time.perf_counter_ns()
            attempts.append(attempt)
            _atomic_json(batch/(attempt.attempt_id+'.json'),{'attempt_id':attempt.attempt_id,
                'call_start_ns':call_start,'call_end_ns':call_end,'scope':'full run_request including accounting audit write'},immutable=True)
        status_audit_start = time.perf_counter_ns()
        success = _audit_schedule_status(out, metadata['request_order'])
        status_audit_end = time.perf_counter_ns()
        status = {'schema_version':1, 'success':success, 'config_hash':metadata['config_hash'],
                  'phase':phase, 'request_count':len(requests), 'audit_end_ns':status_audit_end}
        status_publication_start = time.perf_counter_ns()
        _atomic_json(batch/'status.json', status, immutable=True)
        _atomic_json(out/'schedule-status.json', {'schema_version':1,
            'path':str((batch/'status.json').relative_to(out)), 'sha256':_digest(status)})
        status_publication_end = time.perf_counter_ns()
        collection_end=time.perf_counter_ns()
        audit_start=time.perf_counter_ns()
        _atomic_json(batch/'accounting.json',{'schema_version':1,'collection_end_ns':collection_end,
            'status_audit_ns':status_audit_end-status_audit_start,
            'status_publication_ns':status_publication_end-status_publication_start,
            'status_audit_end_ns':status_audit_end,'status_publication_end_ns':status_publication_end,
            'total_observed_ns':collection_end-batch_start,'coordinator_cpu_ns':time.process_time_ns()-batch_cpu,
            'coordinator_peak_rss_bytes':int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*(1 if sys.platform=='darwin' else 1024),'attempt_ids':[a.attempt_id for a in attempts],
            'report_generation_tail_ns':None,
            'scope':'entry through configuration/resume, serial workers, full request publication/accounting writes, effective-outcome audit and status publication; this final audit write is report-generation overhead'},immutable=True)
        _atomic_json(batch/'reporting.json',{'accounting_audit_write_ns':time.perf_counter_ns()-audit_start,
            'scope':'measured final accounting audit write; this reporting receipt tail remains unmeasured'},immutable=True)
    return attempts


def _audit_schedule_status(out: Path, expected: Sequence[str]) -> bool:
    """Under primary admission, audit effective status including retained faults.

    An external interruption can be superseded by its valid retry; a terminal
    method fault remains an outcome and is never converted to success by resume.
    """
    out = Path(out).resolve()
    effective = {}
    for manifest in sorted((out/'attempts').rglob('attempt.json')):
        payload, final = _read_attempt(manifest.parent)
        identity = payload['request_id']
        if identity not in expected:
            raise ValueError('attempt outside scheduled request identities')
        if final and payload['status'] != 'external_interrupt':
            if identity in effective:
                raise ValueError('duplicate terminal outcome for scheduled request')
            effective[identity] = payload['status']
    return bool(expected) and all(effective.get(identity) in ('complete','deadline','startup_timeout') for identity in expected)


def schedule_succeeded(out: Path) -> bool:
    """Read the bounded hash-validated status published under primary admission.

    The expensive complete-history artifact audit has already been charged inside
    run_schedule. CLI reads only this pointer and its small immutable status file.
    """
    out = Path(out).resolve()
    pointer = strict_json((out/'schedule-status.json').read_text())
    path = (out/pointer['path']).resolve()
    if not path.is_relative_to(out):
        raise ValueError('schedule status path escapes output')
    raw = path.read_bytes()
    if len(raw) > 4096 or hashlib.sha256(raw).hexdigest() != pointer['sha256']:
        raise ValueError('schedule status hash/size mismatch')
    status = strict_json(raw.decode())
    if pointer.get('schema_version') != 1 or status.get('schema_version') != 1 or type(status.get('success')) is not bool:
        raise ValueError('invalid published schedule status')
    return status['success']
