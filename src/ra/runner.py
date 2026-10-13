"""Cold single-request parent with authoritative complete-frame receipt times.

This is a harness primitive. Atomic publication/recovery and the complete disjoint
cost ledger are intentionally owned by Task 7, general run configuration by Task 8.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import time

from ra.metrics import ProgressStream, progress_at, validate_clock_alignment
from ra.types import Attempt, AvailableProgress, ProgressRecord, Request
from ra.worker import Channel, strict_json, validate_request


def _worker_argv(request_path: Path) -> list[str]:
    return [sys.executable, '-m', 'ra.worker', str(request_path)]


def run_request(request: Request, out: Path) -> Attempt:
    validate_request(request)
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / 'solutions').mkdir()
    request_path = out / 'request.json'
    request_path.write_text(json.dumps(asdict(request), sort_keys=True, indent=2) + '\n')
    parent, child = socket.socketpair()
    env = os.environ.copy()
    env['RA_CHANNEL_FD'] = str(child.fileno())
    argv = _worker_argv(request_path)
    records, samples = [], []
    timestamps = {}
    resources = {'clock_samples': samples, 'resource_scope': 'one worker; overlapping parent cost separate',
                 'timing_partition_complete': False, 'argv': argv}
    terminal = None
    stream = None
    aligned = False
    ready = False
    error = None
    parent_failure = False
    censored = False
    stop_sent = False
    parent_cpu = time.process_time_ns()
    observation_ns = 0
    buffer = b''
    process = None
    channel = Channel(parent)
    pending_ping = None
    with (out / 'stdout.log').open('wb') as stdout, (out / 'stderr.log').open('wb') as stderr, \
            (out / 'wire.jsonl').open('w') as wire, (out / 'progress.jsonl').open('w') as progress_file:
        try:
            launch_ns = time.perf_counter_ns()
            process = subprocess.Popen(argv, env=env, pass_fds=(child.fileno(),), stdout=stdout, stderr=stderr)
            request = replace(request, launch_ns=launch_ns, deadline_ns=launch_ns + request.budget_ns)
            timestamps.update(launch_ns=launch_ns, deadline_ns=request.deadline_ns,
                              launched_ns=time.perf_counter_ns())
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
                # Finish bootstrap first: the child checks the absolute deadline
                # before imports. A stop frame cannot be mistaken for a clock ping.
                if aligned and now >= request.deadline_ns and not stop_sent:
                    timestamps['parent_stop_request_ns'] = now
                    try:
                        channel.send({'kind': 'stop'})
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                    stop_sent = True
                if now >= request.deadline_ns + request.watchdog_grace_ns and process.poll() is None:
                    timestamps['watchdog_ns'] = now
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
                            path.write_text(json.dumps(assignment, sort_keys=True) + '\n')
                        elif record.assignment_available and not path.exists():
                            raise ValueError('published assignment array missing')
                        records.append(record)
                        progress_file.write(json.dumps(asdict(record), allow_nan=False) + '\n')
                    elif kind == 'terminal':
                        if terminal is not None:
                            raise ValueError('duplicate terminal record')
                        terminal = packet
                        timestamps.update(packet['timestamps'])
                        timestamps['terminal_receipt_ns'] = receipt
                        resources.update(packet['resources'])
                    else:
                        raise ValueError(f'unknown worker packet: {kind}')
                observation_ns += time.perf_counter_ns() - started
            try:
                process.wait(timeout=max(0., (request.deadline_ns + request.watchdog_grace_ns - time.perf_counter_ns()) / 1e9))
            except subprocess.TimeoutExpired:
                timestamps['watchdog_ns'] = time.perf_counter_ns()
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
            error = f'{type(exc).__name__}: {exc}'
            if process is not None and process.poll() is None:
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
    resources['returncode'] = process.returncode if process is not None else None
    resources['parent_cpu_ns'] = time.process_time_ns() - parent_cpu
    resources['parent_observation_ns_overlapping_worker'] = observation_ns
    resources['trace_bytes'] = sum((out / name).stat().st_size for name in ('wire.jsonl', 'progress.jsonl', 'stdout.log', 'stderr.log'))
    resources['clock_max_bracket_ns'] = max((end - start for start, _, end in samples), default=None)
    timestamps['parent_finalize_ns'] = time.perf_counter_ns()
    deadline = request.deadline_ns or timestamps['parent_finalize_ns']
    attempt = Attempt(request.request_id, status, available, aligned, timestamps, resources,
                      max(0, timestamps['parent_release_ns'] - deadline), censored, error, request)
    (out / 'attempt.json').write_text(json.dumps(asdict(attempt), sort_keys=True, indent=2, allow_nan=False) + '\n')
    return attempt
