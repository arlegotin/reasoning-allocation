"""Callback-local SCIP node access and locally exercised capability evidence.

Only Model ownership persists. Native node/solution/variable wrappers are local to
adapter calls; policies receive immutable primitives. Diagnostic searches below
are capability fixtures, never benchmark data or a primary solver configuration.
"""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict, dataclass, is_dataclass, replace
from functools import wraps
import hashlib
import json
import math
from pathlib import Path
import random
import select
import subprocess
import sys
import time
from typing import Callable, Sequence

from pyscipopt import Eventhdlr, Model, Nodesel, SCIP_EVENTTYPE as E, SCIP_PARAMSETTING as P, SCIP_NODETYPE as N, SCIP_STAGE as S, quicksum

from ra.types import NodeKey, NodeRecord, SelectionBoundary
from ra.leases import LeaseController
from ra.observer import Observer, NumericalAlarm


class StaleNodeError(ValueError):
    """A primitive key does not designate an open node in this native run."""


class AdapterError(RuntimeError):
    """Native evidence violates the adapter's correctness contract."""


class CallbackError(AdapterError):
    """A nonstandard callback exception, with its original primitive provenance."""


from ra.ledger import timed


def _contain_callback(method):
    """Never propagate Python exceptions through PySCIPOpt's noexcept boundary."""
    measured = timed('callback')(method)
    @wraps(method)
    def contained(plugin, *args):
        try:
            return measured(plugin, *args)
        except BaseException as exc:
            plugin.backend._capture_fault(exc, method.__name__)
            if method.__name__ == 'nodeselect':
                # Timing can fail before the selector body or after its return.
                # Native still needs an open node while the stop request unwinds.
                legal_node = None
                try:
                    for nodes in plugin.backend.model.getOpenNodes():
                        if nodes:
                            legal_node = nodes[0]
                            break
                except BaseException as secondary:
                    plugin.backend._capture_fault(secondary, 'nodeselect_unwind')
                return {'selnode': legal_node}
            # Comparison still needs a legal equality result on fault.
            return 0 if method.__name__ == 'nodecomp' else None
    return contained


@dataclass(frozen=True, slots=True)
class Completion:
    key: NodeKey
    main_tree: bool
    event_kind: str


_COMPLETION_EVENTS = {E.NODEFEASIBLE: 'NODEFEASIBLE', E.NODEINFEASIBLE: 'NODEINFEASIBLE',
                      E.NODEBRANCHED: 'NODEBRANCHED'}
_EVENT_NAMES = {**_COMPLETION_EVENTS, E.NODEDELETE: 'NODEDELETE', E.NODEFOCUSED: 'NODEFOCUSED',
                E.BESTSOLFOUND: 'BESTSOLFOUND', E.DUALBOUNDIMPROVED: 'DUALBOUNDIMPROVED'}
_EVENT_MASK = E.NODESOLVED | E.NODEDELETE | E.NODEFOCUSED | E.BESTSOLFOUND | E.DUALBOUNDIMPROVED


def compare_nodes(left: object, right: object) -> int:
    """SCIP comparator: greatest immutable depth, then smallest number."""
    a = (-left.getDepth(), left.getNumber())
    b = (-right.getDepth(), right.getNumber())
    return (a > b) - (a < b)


class ScipBackend:
    """Own a main SCIP model and copy live search state into primitive records.

    The optional selector consumes primitives and returns a key. Event handlers
    are not copied into sub-SCIPs; only this model's registered callbacks credit
    work. Costs/rows describe the independent original binary cover verifier.
    """
    def __init__(self, model: Model, *, costs: Sequence[int], rows: Sequence[Sequence[int]],
                 variable_names: Sequence[str] | None = None, objective_scale: int = 1,
                 objective_offset: int = 0,
                 choose: Callable[[list[NodeRecord]], NodeKey] | None = None,
                 lease_controller: LeaseController | None = None,
                 observer: Observer | None = None, install_selector: bool = True,
                 deadline_ns: int | None = None, stop_poll: Callable[[], bool] | None = None):
        if not costs or any(type(c) is not int or c <= 0 for c in costs):
            raise ValueError('cover costs must be positive integers')
        if objective_scale <= 0 or type(objective_scale) is not int or type(objective_offset) is not int:
            raise ValueError('objective requires positive integer scale and integer offset')
        self.costs = tuple(costs)
        self.rows = tuple(tuple(row) for row in rows)
        if not self.rows or any(not row or len(set(row)) != len(row) or
                                any(type(i) is not int or not 0 <= i < len(costs) for i in row)
                                for row in self.rows):
            raise ValueError('invalid original cover incidence')
        self.variable_names = tuple(variable_names or (f'x{i}' for i in range(len(costs))))
        if len(self.variable_names) != len(costs) or len(set(self.variable_names)) != len(costs):
            raise ValueError('original variable names must be unique and match costs')
        self.model = model
        self.scale, self.offset = objective_scale, objective_offset
        if not install_selector and (choose is not None or lease_controller is not None):
            raise ValueError("native observation cannot install a custom policy or lease")
        self.observer = observer
        self.deadline_ns, self.stop_poll = deadline_ns, stop_poll
        self.progress_subscriptions = 0
        self.progress_events: Counter[str] = Counter()
        self.choose = choose
        self.lease_controller = lease_controller
        self.epoch = 0
        self.native_run: int | None = None
        self.run_transitions: list[dict[str, int]] = []
        self.parents: dict[NodeKey, NodeKey | None] = {}
        if lease_controller is not None:
            lease_controller.parents = self.parents
            if lease_controller.request_stop is None:
                lease_controller.request_stop = self.request_stop
        self.depths: dict[NodeKey, int] = {}
        self.ancestor_references: dict[NodeKey, int] = {}
        self.first_seen: dict[NodeKey, int] = {}
        self.deleted: set[NodeKey] = set()
        self.completions: list[Completion] = []
        self._completed: set[NodeKey] = set()
        self.events: Counter[str] = Counter()
        self.non_search_events: Counter[str] = Counter()
        self._tree_active = False
        self.selection_count = 0
        self.init_calls = self.exit_calls = self.subscriptions = 0
        self.stop_requested = False
        self.stop_request_ns: int | None = None
        self.callback_fault: dict[str, object] | None = None
        self.safe_return_ns: int | None = None
        self.last_callback_entry_ns: int | None = None
        self.last_callback_end_ns: int | None = None
        self.last_dispatch_ns: int | None = None
        self.selection_boundaries: list[SelectionBoundary] = []
        self._callback_depth = 0
        self._transformed_once = False
        self.selector = _Selector(self) if install_selector else None
        self.handler = _Events(self) if install_selector else None
        if install_selector:
            model.includeNodesel(self.selector, 'ra-live', 'primitive live-node adapter', 1000000, 1000000)
            model.includeEventhdlr(self.handler, 'ra-events', 'main-tree lifecycle observer')
        self.progress_handler = _ProgressEvents(self) if observer is not None else None
        if self.progress_handler is not None:
            model.includeEventhdlr(self.progress_handler, 'ra-progress', 'common original-space observer')

    def _capture_fault(self, exc: BaseException, callback: str) -> None:
        if self.lease_controller is not None:
            self.lease_controller.cancel('callback_error')
        if self.callback_fault is None:
            frames = []
            tb = exc.__traceback__
            while tb is not None:
                frames.append({'file': tb.tb_frame.f_code.co_filename,
                               'function': tb.tb_frame.f_code.co_name, 'line': tb.tb_lineno})
                tb = tb.tb_next
            self.callback_fault = {
                'exception_module': type(exc).__module__, 'exception_type': type(exc).__name__,
                'message': str(exc), 'callback': callback, 'stage': int(self.model.getStage()),
                'epoch': self.epoch, 'native_run': self.native_run, 'frames': frames,
                'status': ('numerical_alarm' if isinstance(exc, (AdapterError, NumericalAlarm)) else
                           'oom' if isinstance(exc, MemoryError) else 'implementation_error'),
                'timestamp_ns': time.perf_counter_ns()}
        # Store only primitives; never retain exc or its traceback/native callback locals.
        if not self.stop_requested:
            self.stop_requested = True
            self.stop_request_ns = time.perf_counter_ns()
        self._apply_pending_stop()

    def _apply_pending_stop(self) -> None:
        # In EXITPRESOLVE/teardown, retain the request and return to SCIP normally.
        # The next solving callback applies it, or presolve terminates safely first.
        if self.stop_requested and self.model.getStage() in (S.PRESOLVING, S.SOLVING):
            self.model.interruptSolve()

    def raise_if_failed(self) -> None:
        """Raise a fresh exception after native return; provenance stays primitive."""
        fault = self.callback_fault
        if fault is None:
            return
        # Only these exact types have a supported one-message constructor. Never
        # invoke arbitrary built-in/custom constructors from primitive metadata.
        message_types = (AdapterError, NumericalAlarm, StaleNodeError, Exception, RuntimeError,
                         ValueError, TypeError, AssertionError, MemoryError, KeyboardInterrupt, SystemExit)
        error_type = next((cls for cls in message_types
                           if (cls.__module__, cls.__name__) ==
                           (fault['exception_module'], fault['exception_type'])), CallbackError)
        error = error_type(fault['message'])
        error.callback_fault = dict(fault)
        raise error from None

    @timed('administration')
    def optimize(self) -> None:
        """Solve through this boundary to preserve callback faults after safe return.

        Direct Model.optimize callers must call raise_if_failed themselves; validated
        progress also refuses results after any callback fault. A faulted adapter is
        terminal and must not be resumed as a successful request.
        """
        self.raise_if_failed()
        try:
            ledger = getattr(self, 'time_ledger', None)
            if ledger is not None:
                ledger.enter('native', time.perf_counter_ns())
            try:
                self.model.optimize()
            finally:
                if ledger is not None:
                    ledger.leave(time.perf_counter_ns())
        except BaseException:
            self.raise_if_failed()
            raise
        finally:
            self.safe_return_ns = time.perf_counter_ns()
            if self.lease_controller is not None:
                status = str(self.model.getStatus())
                self.lease_controller.cancel('terminal' if status in ('optimal', 'infeasible', 'unbounded')
                                             else 'deadline' if status == 'timelimit' else 'search_exit')
                if self.lease_controller.pending:
                    self.lease_controller.finish(self.safe_return_ns, 'search_exit')
        self.raise_if_failed()
        if self.observer is not None:
            try:
                self.observer.poll(self.model, self.variable_names, time.perf_counter_ns())
            except BaseException as exc:
                self._capture_fault(exc, "terminal_observation")
                self.raise_if_failed()

    @property
    def processed_nodes(self) -> int:
        return len(self.completions)

    def _clear_tree(self) -> None:
        if self.lease_controller is not None:
            self.lease_controller.cancel('restart')
        self.parents.clear()
        self.depths.clear()
        self.first_seen.clear()
        self.ancestor_references.clear()
        self.deleted.clear()

    def _sync_run(self) -> None:
        run = int(self.model.getNRuns())
        if self.native_run is not None and run != self.native_run:
            self.run_transitions.append({'before': self.native_run, 'after': run,
                                         'old_epoch': self.epoch, 'new_epoch': self.epoch + 1})
            self.epoch += 1
            self._clear_tree()
        self.native_run = run

    @contextmanager
    def _callback(self):
        self._callback_depth += 1
        try:
            self._sync_run()
            yield
        finally:
            self._callback_depth -= 1

    def _require_callback(self) -> None:
        if not self._callback_depth:
            raise RuntimeError('live native node access requires an adapter callback')

    def _capture_ancestry(self, node) -> NodeKey:
        key = NodeKey(self.epoch, int(node.getNumber()))
        current = node
        seen = set()
        while current is not None:
            child_key = NodeKey(self.epoch, int(current.getNumber()))
            depth = int(current.getDepth())
            if child_key in seen:
                raise AdapterError('cyclic native ancestry')
            seen.add(child_key)
            parent = current.getParent()
            parent_key = NodeKey(self.epoch, int(parent.getNumber())) if parent is not None else None
            if (parent is None) != (depth == 0):
                raise AdapterError('missing native ancestor')
            if parent is not None and int(parent.getDepth()) != depth - 1:
                raise AdapterError('inconsistent native ancestor depth')
            if child_key in self.parents and self.parents[child_key] != parent_key:
                raise AdapterError('native node number reused within an epoch')
            self.parents[child_key] = parent_key
            self.depths[child_key] = depth
            self.first_seen.setdefault(child_key, self.selection_count)
            current = parent
        return key

    def _path(self, key: NodeKey) -> list[NodeKey]:
        path = []
        while key is not None:
            if key not in self.parents:
                raise AdapterError('missing primitive ancestor')
            path.append(key)
            key = self.parents[key]
        return path

    def live_frontier(self) -> list[NodeRecord]:
        self._require_callback()
        self._sync_run()
        records = {}
        references: Counter[NodeKey] = Counter()
        for category, nodes in zip(('leaf', 'child', 'sibling'), self.model.getOpenNodes()):
            for node in nodes:
                key = self._capture_ancestry(node)
                if key in records:
                    continue
                if key in self.deleted:
                    raise AdapterError('deleted node returned by native open list')
                path = self._path(key)
                references.update(path)
                digest = hashlib.sha256('/'.join(f'{k.epoch}:{k.number}' for k in path).encode()).hexdigest()
                records[key] = NodeRecord(key, self.parents[key], int(node.getDepth()),
                                          float(node.getLowerbound()), float(node.getEstimate()),
                                          self.first_seen[key], digest, category,
                                          int(node.getNParentBranchings()))
        # Ancestors outlive their own processing only while an open descendant needs them.
        self.ancestor_references = dict(references)
        for mapping in (self.parents, self.depths, self.first_seen):
            for key in list(mapping):
                if key not in references:
                    del mapping[key]
        return list(records.values())

    def resolve_live(self, key: NodeKey) -> object:
        self._require_callback()
        self._sync_run()
        if key.epoch != self.epoch or key in self.deleted:
            raise StaleNodeError(f'node {key} is no longer live')
        for nodes in self.model.getOpenNodes():
            for node in nodes:
                if int(node.getNumber()) == key.number:
                    return node
        raise StaleNodeError(f'node {key} is not in the current open frontier')

    def record_completion(self, key: NodeKey, event_kind: str, *, main_tree: bool) -> None:
        """Consume a primitive native event once; deletion never invokes this path."""
        if event_kind not in _COMPLETION_EVENTS.values():
            raise AdapterError(f'not a completed-node event: {event_kind}')
        if not main_tree or key in self._completed:
            return
        self._completed.add(key)
        self.completions.append(Completion(key, main_tree, event_kind))
        if self.lease_controller is not None:
            self.lease_controller.on_completed(key)

    def _on_event(self, event) -> None:
        kind = int(event.getType())
        self.events[_EVENT_NAMES[kind]] += 1
        if not self._tree_active:
            self.non_search_events[_EVENT_NAMES[kind]] += 1
            return
        if kind & (E.NODESOLVED | E.NODEDELETE | E.NODEFOCUSED):
            node = event.getNode()
            key = NodeKey(self.epoch, int(node.getNumber()))
            if int(node.getType()) == N.PROBINGNODE:
                return  # Probing nodes are temporary native work, not main-tree credit.
            if kind in _COMPLETION_EVENTS:
                self.record_completion(key, _COMPLETION_EVENTS[kind], main_tree=True)
            elif kind == E.NODEDELETE:
                self.deleted.add(key)
                if self.lease_controller is not None:
                    self.lease_controller._on_deleted(key)

    def validated_progress(self) -> tuple[float, float, float]:
        """Check original assignment using Python integers; keep native bounds separate."""
        self.raise_if_failed()
        if self.observer is not None:
            return self.observer.available_local()
        dual = float(self.model.getDualbound())
        if self.model.isInfinity(abs(dual)):
            if dual > 0:
                raise AdapterError('infinite positive dual for feasible cover')
            dual = float(self.offset)  # Proven structural bound for positive cover costs.
        if not math.isfinite(dual):
            raise AdapterError('nonfinite original dual')
        sol = self.model.getBestSol()
        if sol is None:
            return math.inf, dual, 0.0
        variables = {v.name: v for v in self.model.getVars(transformed=False)}
        if set(variables) != set(self.variable_names):
            raise AdapterError('original variable schema mismatch')
        tolerance = float(self.model.getParam('numerics/feastol'))
        assignment = []
        for name in self.variable_names:
            value = float(self.model.getSolVal(sol, variables[name]))
            if not math.isfinite(value) or abs(value - round(value)) > tolerance or round(value) not in (0, 1):
                raise AdapterError('nonbinary original assignment')
            assignment.append(int(round(value)))
        if any(sum(assignment[i] for i in row) < 1 for row in self.rows):
            raise AdapterError('infeasible original assignment')
        primal = self.scale * sum(c * x for c, x in zip(self.costs, assignment)) + self.offset
        native_primal = float(self.model.getSolObjVal(sol, original=True))
        if not math.isfinite(native_primal) or abs(native_primal - primal) > tolerance:
            raise AdapterError('original objective mismatch')
        if dual > primal + tolerance:
            raise AdapterError('original dual exceeds verified primal')
        return float(primal), dual, 1.0 - (primal - dual) / (self.scale * sum(self.costs))

    def request_stop(self) -> None:
        self._require_callback()
        if not self.stop_requested:
            self.stop_request_ns = time.perf_counter_ns()
            self.stop_requested = True
        self._apply_pending_stop()


class _Selector(Nodesel):
    def __init__(self, backend):
        self.backend = backend

    @_contain_callback
    def nodeinit(self):
        b = self.backend
        if b._transformed_once:
            b.epoch += 1
            b.native_run = None
            b._clear_tree()
        if b.callback_fault is None:
            b.stop_requested = False
            b.stop_request_ns = None
        b._transformed_once = True

    @_contain_callback
    def nodeinitsol(self):
        self.backend._tree_active = True
        self.backend.init_calls += 1
        self.backend._sync_run()
        self.backend._apply_pending_stop()

    @_contain_callback
    def nodeexitsol(self):
        self.backend._tree_active = False
        self.backend.exit_calls += 1

    @_contain_callback
    def nodecomp(self, left, right):
        return compare_nodes(left, right)

    @_contain_callback
    def nodeselect(self):
        b = self.backend
        b.last_callback_entry_ns = time.perf_counter_ns()
        lease = b.lease_controller
        boundary_index = None
        if lease is not None:
            known = not lease.active
            boundary_index = len(b.selection_boundaries)
            b.selection_boundaries.append(SelectionBoundary(b.last_callback_entry_ns,
                None, None, None, 'rebid' if known else 'provisional',
                'known' if known else 'provisional', None))

        def boundary(**changes):
            if boundary_index is not None:
                b.selection_boundaries[boundary_index] = replace(b.selection_boundaries[boundary_index], **changes)

        def close_at_entry(reason):
            if lease is not None and lease.pending:
                lease.finish(b.last_callback_entry_ns, reason)

        # Acquire a legal return node before running fallible policy/record logic.
        # On failure it is used only to unwind a failed request, never as a policy fallback.
        legal_node = None
        try:
            # Known rebid transition precedes every native/frontier scan. An
            # active grant keeps a provisional entry until continuation resolves.
            if lease is not None and not lease.active:
                close_at_entry('rebid')
            for nodes in b.model.getOpenNodes():
                if nodes:
                    legal_node = nodes[0]
                    break
            with b._callback():
                b._apply_pending_stop()
                if b.callback_fault is not None:
                    boundary(kind='residual', reason='callback_error')
                    close_at_entry('callback_error')
                    return {'selnode': legal_node}
                b.selection_count += 1
                if lease is not None:
                    if lease.active:
                        lease._deadline(b.last_callback_entry_ns)
                    if not lease.active:
                        close_at_entry('rebid')
                        boundary(kind='residual' if b.stop_requested else 'rebid', origin='known',
                                 reason='deadline' if b.stop_requested else None)
                continuing = lease is not None and lease.active
                scan_start = time.perf_counter_ns()
                records = b.live_frontier()
                scan_end = time.perf_counter_ns()
                boundary(snapshot_ns=scan_end)
                key = lease.next_node(records, scan_end) if lease is not None else None
                if continuing and key is not None:
                    lease._charge_continuation_scan(scan_end - scan_start)
                    boundary(kind='continuation')
                if not records:
                    close_at_entry('exhaustion')
                    boundary(kind='residual', origin='discovered' if continuing else 'known', reason='empty_tree')
                    return {'selnode': None}
                if key is None:
                    close_at_entry('rebid')
                    boundary(kind='residual' if b.stop_requested else 'rebid',
                             origin='discovered' if continuing else 'known',
                             reason='deadline' if b.stop_requested else None)
                    if b.stop_requested:
                        key = min(records, key=lambda n: (-n.depth, n.key.number)).key
                    else:
                        key = b.choose(records) if b.choose else min(records, key=lambda n: (-n.depth, n.key.number)).key
                        if lease is not None and lease.pending:
                            # Validate grant provenance independently of next_node:
                            # an unavailable initial root is never natural exhaustion.
                            if lease.root not in {record.key for record in records}:
                                raise StaleNodeError('allocation root is not in the current open frontier')
                            if lease.root != key:
                                raise AdapterError('allocation root differs from chosen node')
                        if lease is not None and lease.active:
                            leased_key = lease.next_node(records, time.perf_counter_ns())
                            if leased_key is not None:
                                if leased_key != key:
                                    raise AdapterError('allocation root differs from chosen node')
                                key = leased_key
                node = b.resolve_live(key)
                b.last_dispatch_ns = time.perf_counter_ns()
                boundary(dispatch_ns=b.last_dispatch_ns)
                if lease is not None:
                    lease.mark_dispatch(b.last_dispatch_ns)
                return {'selnode': node}
        except BaseException as exc:
            b._capture_fault(exc, 'nodeselect')
            current = b.selection_boundaries[boundary_index] if boundary_index is not None else None
            if current is None or current.kind != 'continuation':
                # Uncertain scan or failed administration has no selected new
                # action. Keep its full callback interval as explicit residual.
                close_at_entry('callback_error')
                boundary(kind='residual', reason='callback_error')
            else:
                boundary(reason='callback_error')
            return {'selnode': legal_node}
        finally:
            b.last_callback_end_ns = time.perf_counter_ns()
            boundary(end_ns=b.last_callback_end_ns)


class _ProgressEvents(Eventhdlr):
    """Identical lightweight observer on both routes; no node/frontier access."""
    timing_category = 'observation'
    mask = E.BESTSOLFOUND | E.DUALBOUNDIMPROVED | E.NODESOLVED | E.PRESOLVEROUND

    def __init__(self, backend):
        self.backend = backend

    @_contain_callback
    def eventinit(self):
        self.model.catchEvent(self.mask, self)
        self.backend.progress_subscriptions += 1

    @_contain_callback
    def eventexit(self):
        self.model.dropEvent(self.mask, self)
        self.backend.progress_subscriptions -= 1

    @_contain_callback
    def eventexec(self, event):
        b = self.backend
        now = time.perf_counter_ns()
        b.progress_events[str(int(event.getType()))] += 1
        with b._callback():
            if (b.deadline_ns is not None and now >= b.deadline_ns
                    or b.stop_poll is not None and b.stop_poll()):
                b.request_stop()
            b._apply_pending_stop()
            if b.callback_fault is None:
                b.observer.poll(b.model, b.variable_names, now)


class _Events(Eventhdlr):
    def __init__(self, backend):
        self.backend = backend

    @_contain_callback
    def eventinit(self):
        self.model.catchEvent(_EVENT_MASK, self)
        self.backend.subscriptions += 1

    @_contain_callback
    def eventexit(self):
        self.model.dropEvent(_EVENT_MASK, self)
        self.backend.subscriptions -= 1

    @_contain_callback
    def eventexec(self, event):
        with self.backend._callback():
            self.backend._apply_pending_stop()
            if self.backend.callback_fault is None:
                self.backend._on_event(event)


# Small deterministic discovery fixtures; no protected population or training state.
def _case_definition(name: str) -> dict[str, object]:
    if name == 'descendant_propagation':
        return {'costs': [1, 1, 1], 'rows': [[0, 1], [0, 2], [1, 2]],
                'scale': 1, 'offset': 0, 'altered_enhancements': True,
                'parameter_overrides': {'branching/mostinf/priority': 1000000}}
    if name == 'propagation':
        return {'costs': [1], 'rows': [[0]], 'scale': 1, 'offset': 0, 'altered_enhancements': True}
    if name in ('normal', 'affine'):
        return {'costs': [1, 2, 1], 'rows': [[0, 1], [1, 2]],
                'scale': 3 if name == 'affine' else 1, 'offset': 5 if name == 'affine' else 0,
                'altered_enhancements': False}
    rng = random.Random(71)
    return {'costs': [1 + i % 7 for i in range(100)],
            'rows': [sorted(rng.sample(range(100), 8)) for _ in range(100)],
            'scale': 1, 'offset': 0, 'altered_enhancements': True}


class _CapabilityProbe(ScipBackend):
    """Instrumented adapter used only by capability discovery."""
    def __init__(self, *args, case_name: str, **kwargs):
        self.case_name = case_name
        self.deleted_rejections = self.old_rejections = self.unprocessed_deletions = 0
        self.deletion_credit = self.legal_selections = self.legal_after_stop = self.max_refs = 0
        self.seen_keys: set[NodeKey] = set()
        self.prior_key: NodeKey | None = None
        self.restart_requested = False
        self.root_completions = 0
        self.focused_keys: set[NodeKey] = set()
        self.uncompleted_focused_deletions = 0
        self.node_events: list[dict[str, object]] = []
        self.frontier_keys: set[NodeKey] = set()
        super().__init__(*args, choose=self._choose_diagnostic, **kwargs)

    def _choose_diagnostic(self, records):
        key = min(records, key=lambda n: (-n.depth, n.key.number)).key
        self.seen_keys.update(r.key for r in records)
        self.frontier_keys.update(r.key for r in records)
        if self.prior_key is not None and self.prior_key.epoch != self.epoch:
            try:
                self.resolve_live(self.prior_key)
            except StaleNodeError:
                self.old_rejections += 1
            else:
                raise AdapterError('old epoch resolved after restart')
        self.prior_key = key
        self.max_refs = max(self.max_refs, max(self.ancestor_references.values(), default=0))
        if self.case_name == 'interrupt' and self.processed_nodes >= 1:
            self.request_stop()
        native = self.resolve_live(key)
        if native.getNumber() != key.number:
            raise AdapterError('selector resolved wrong node')
        self.legal_selections += 1
        self.legal_after_stop += int(self.stop_requested)
        return key

    def _on_event(self, event):
        kind = int(event.getType())
        before = self.processed_nodes
        if kind & (E.NODESOLVED | E.NODEDELETE | E.NODEFOCUSED):
            node = event.getNode()
            key = NodeKey(self.epoch, int(node.getNumber()))
            self.node_events.append({'kind': _EVENT_NAMES[kind], 'event_type': kind,
                'epoch': self.epoch, 'run': self.native_run, 'number': key.number,
                'depth': int(node.getDepth()), 'node_type': int(node.getType()),
                'stage': int(self.model.getStage()), 'probing': bool(self.model.inProbing()),
                'main_tree': self._tree_active, 'ever_in_frontier': key in self.frontier_keys,
                'native_processed': int(self.model.getNNodes()),
                'native_lp_iterations': int(self.model.getNLPIterations()) if self.model.getStage() == S.SOLVING else None,
                'native_lp_count': int(self.model.getNLPs()) if self.model.getStage() == S.SOLVING else None,
                'completed_before_event': before})
        super()._on_event(event)
        if not self._tree_active:
            return
        if kind & (E.NODESOLVED | E.NODEDELETE | E.NODEFOCUSED):
            node = event.getNode()
            key = NodeKey(self.epoch, int(node.getNumber()))
            self.seen_keys.add(key)
            if kind == E.NODEFOCUSED:
                self.focused_keys.add(key)
            if kind in _COMPLETION_EVENTS and node.getDepth() == 0:
                self.root_completions += 1
            if kind == E.NODEDELETE:
                try:
                    self.resolve_live(key)
                except StaleNodeError:
                    self.deleted_rejections += 1
                else:
                    raise AdapterError('deleted key resolves')
                if key not in self._completed:
                    if key in self.focused_keys:
                        self.uncompleted_focused_deletions += 1
                    else:
                        self.unprocessed_deletions += 1
                    self.deletion_credit += self.processed_nodes - before
            if self.case_name == 'restart' and kind == E.NODEBRANCHED and not self.restart_requested:
                self.prior_key = key
                self.restart_requested = True
                self.model.restartSolve()


def _run_case(name: str) -> dict[str, object]:
    fixture = _case_definition(name)
    model = Model(f'capability-{name}')
    result = None
    model.hideOutput()
    try:
        defaults = model.getParams()
        model.setIntParam('parallel/maxnthreads', 1)
        model.setIntParam('lp/threads', 1)
        model.setRealParam('limits/time', 5.0)
        if fixture['altered_enhancements']:
            model.setPresolve(P.OFF)
            model.setHeuristics(P.OFF)
            model.setSeparating(P.OFF)
            # setPresolve(OFF) also sets this to zero; restore native restart permission.
            model.setIntParam('presolving/maxrestarts', -1)
        for parameter, value in fixture.get('parameter_overrides', {}).items():
            model.setParam(parameter, value)
        costs, rows = fixture['costs'], fixture['rows']
        x = [model.addVar(name=f'x{i}', vtype='B', obj=fixture['scale'] * cost)
             for i, cost in enumerate(costs)]
        model.addObjoffset(fixture['offset'])
        for row in rows:
            model.addCons(quicksum(x[i] for i in row) >= 1)
        del x  # Native variable wrappers are not retained by the adapter.
        backend = _CapabilityProbe(model, costs=costs, rows=rows,
                                   objective_scale=fixture['scale'], objective_offset=fixture['offset'],
                                   case_name=name)
        parameters = model.getParams()
        started = time.perf_counter_ns()
        backend.optimize()
        elapsed = time.perf_counter_ns() - started
        primal, dual, utility = backend.validated_progress()
        result = {'altered_enhancements': fixture['altered_enhancements'],
                  'fixture_sha256': hashlib.sha256(json.dumps(fixture, sort_keys=True).encode()).hexdigest(),
                  'parameter_changes': {k: v for k, v in parameters.items() if k not in defaults or defaults[k] != v},
                  'restart_parameters': {k: v for k, v in parameters.items() if 'restart' in k},
                  'enhancement_parameter_changes': {k: v for k, v in parameters.items()
                      if k in defaults and defaults[k] != v and k not in ('parallel/maxnthreads', 'lp/threads', 'limits/time')},
                  'status': str(model.getStatus()), 'primal_original': primal,
                  'dual_original': dual, 'utility_local': utility,
                  'transformed_objective': float(model.getObjVal(original=False)) if model.getNSols() else None,
                  'scip_version': f'{model.getMajorVersion()}.{model.getMinorVersion()}.{model.getTechVersion()}',
                  'native_runs': int(model.getNRuns()), 'native_nodes_last_run': int(model.getNNodes()),
                  'native_total_nodes': int(model.getNTotalNodes()), 'native_lps': int(model.getNLPs()),
                  'elapsed_ns': elapsed, 'stop_requested': backend.stop_requested,
                  'stop_request_ns': backend.stop_request_ns, 'safe_return_ns': started + elapsed}
        model.freeProb()  # Exercise deletion and registration cleanup while model still owns nodes.
        backend.raise_if_failed()
        result.update({'completion_count': backend.processed_nodes,
                       'completions': [asdict(c) for c in backend.completions],
                       'node_events': backend.node_events,
                       'root_completions': backend.root_completions,
                       'events': dict(backend.events), 'non_search_events': dict(backend.non_search_events), 'init_calls': backend.init_calls,
                       'exit_calls': backend.exit_calls, 'subscriptions_after_free': backend.subscriptions,
                       'run_transitions': backend.run_transitions,
                       'deleted_key_rejections': backend.deleted_rejections,
                       'old_epoch_rejections': backend.old_rejections,
                       'unprocessed_deletions': backend.unprocessed_deletions,
                       'uncompleted_focused_deletions': backend.uncompleted_focused_deletions,
                       'credit_from_unprocessed_deletions': backend.deletion_credit,
                       'legal_selections': backend.legal_selections,
                       'legal_selections_after_stop': backend.legal_after_stop,
                       'max_ancestor_references': backend.max_refs,
                       'selection_contract': 'selnode', 'stale_exception': 'StaleNodeError',
                       'reused_numbers': sorted(n for n, count in Counter(k.number for k in backend.seen_keys).items() if count > 1)})
        # Serialization rejects accidental native wrappers in persistent evidence.
        json.dumps(result, allow_nan=False)
        result['history_contains_only_primitives'] = _primitive_history(backend)
        # Compare cumulative main LP iterations at consecutive completion events.
        previous_iterations = {}
        without_new_iterations = 0
        for event in backend.node_events:
            if event['main_tree'] and event['kind'] in _COMPLETION_EVENTS.values():
                previous = previous_iterations.get(event['epoch'], 0)
                without_new_iterations += int(event['native_lp_iterations'] == previous)
                previous_iterations[event['epoch']] = event['native_lp_iterations']
        result['completions_without_new_lp_iterations'] = without_new_iterations
        focused = {}
        no_lp_descendants = []
        for event in backend.node_events:
            key = (event['epoch'], event['number'])
            if event['kind'] == 'NODEFOCUSED' and event['main_tree']:
                focused[key] = event
            elif event['kind'] in _COMPLETION_EVENTS.values() and event['main_tree']:
                focus = focused.pop(key)
                if event['depth'] > 0 and focus['native_lp_count'] == event['native_lp_count']:
                    no_lp_descendants.append(event['number'])
        result['selected_no_lp_descendants_with_completion'] = no_lp_descendants
        result['focused_without_completion'] = [list(key) for key in sorted(focused)]
        result['counter_difference'] = result['native_total_nodes'] - result['completion_count']
        result['counter_note'] = ('Native total counts processed nodes across runs; completed-event count '
                                  'includes emitted root completions. Propagation-only optimality or interruption can leave a focused '
                                  'node without a completion; deleted unprocessed nodes receive no credit.')
        return result
    except BaseException as exc:
        failure = {'case': name, 'status': 'implementation_error',
                   'safe_return_ns': backend.safe_return_ns if 'backend' in locals() else None}
        if 'backend' in locals() and backend.callback_fault is not None:
            failure['status'] = backend.callback_fault['status']
            exc.callback_fault = dict(backend.callback_fault)
        exc.failed_case = failure
        result = failure
        raise
    finally:
        model.free()
        if result is not None:
            result['native_release_ns'] = time.perf_counter_ns()
            result['plugin_models_released'] = ('backend' not in locals() or
                (backend.selector.model is None and backend.handler.model is None))


def _primitive_history(backend: ScipBackend) -> bool:
    def primitive(value):
        if value is None or isinstance(value, (str, int, float, bool)):
            return True
        if is_dataclass(value):
            return primitive(asdict(value))
        if isinstance(value, dict):
            return all(primitive(k) and primitive(v) for k, v in value.items())
        if isinstance(value, (list, tuple, set)):
            return all(primitive(v) for v in value)
        return False
    return all(primitive(v) for k, v in vars(backend).items()
               if k not in ('model', 'selector', 'handler', 'choose'))


def _clock_evidence() -> dict[str, object]:
    # Ping-pong bounds require no assumption about subprocess startup latency.
    child = subprocess.Popen([sys.executable, '-u', '-c',
        'import sys,time\nfor line in sys.stdin:\n print(time.perf_counter_ns(), flush=True)'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    samples = []
    try:
        for _ in range(5):
            sent = time.perf_counter_ns()
            child.stdin.write('ping\n')
            child.stdin.flush()
            if not select.select([child.stdout], [], [], 5)[0]:
                child.kill()
                raise AdapterError('monotonic clock child did not respond')
            value = int(child.stdout.readline())
            received = time.perf_counter_ns()
            samples.append({'parent_send_ns': sent, 'child_ns': value, 'parent_receive_ns': received,
                            'round_trip_ns': received - sent})
    finally:
        child.communicate(timeout=5)
    return {'comparable': all(s['parent_send_ns'] <= s['child_ns'] <= s['parent_receive_ns'] for s in samples),
            'clock': 'time.perf_counter_ns', 'implementation': time.get_clock_info('perf_counter').implementation,
            'samples': samples, 'scope': 'cheap local comparability check; full deadline/receipt harness is WP02'}


def capture_capabilities(out: Path) -> dict[str, object]:
    """Exercise mandatory native capabilities; missing evidence fails the gate."""
    import pyscipopt
    started = time.perf_counter_ns()
    cpu_started = time.process_time_ns()
    report = {'schema_version': 1, 'evidence_label': 'locally measured check',
              'success': False, 'cases': {}, 'operations': {}, 'errors': [],
              'pyscipopt_version': pyscipopt.__version__}
    operations = report['operations']
    def require(name, passed, evidence):
        operations[name] = {'status': 'exercised' if passed else 'blocked', 'evidence': evidence}
    try:
        import resource
        source = Path(pyscipopt.__file__).parent / 'scip.pxi'
        report['run_identity'] = {'api': 'Model.getNRuns', 'source': str(source),
                                  'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                                  'bridge_required': False}
        for name in ('normal', 'affine', 'branching', 'restart', 'interrupt', 'propagation', 'descendant_propagation'):
            report['cases'][name] = _run_case(name)
        cases = report['cases']
        normal, affine, branch, restart, stop = (cases[k] for k in ('normal', 'affine', 'branching', 'restart', 'interrupt'))
        require('normal_enhancements', normal['primal_original'] == normal['dual_original'] == 2
                and not normal['enhancement_parameter_changes'],
                'normal cover solve preserves native enhancement defaults')
        require('original_transformed_objectives', affine['primal_original'] == affine['dual_original'] == 11
                and affine['transformed_objective'] != 11, '3*objective+5 checked against original binary assignment')
        require('live_selection', branch['legal_selections'] > 1 and all(c['history_contains_only_primitives'] for c in cases.values()), 'native selnode callback mapping and fresh open-list resolution')
        require('ancestry', branch['max_ancestor_references'] > 0, 'live ancestry captured and retained by descendant references')
        require('deletion', branch['deleted_key_rejections'] > 0 and branch['unprocessed_deletions'] > 0
                and branch['credit_from_unprocessed_deletions'] == 0, 'deleted keys rejected; unprocessed deletion gives zero credit')
        require('completion', branch['completion_count'] == branch['native_total_nodes'] and branch['root_completions'] == 1
                and cases['propagation']['completion_count'] == 0 and cases['propagation']['native_total_nodes'] == 1
                and cases['propagation']['uncompleted_focused_deletions'] == 1
                and cases['propagation']['native_lps'] == 0
                and bool(cases['descendant_propagation']['selected_no_lp_descendants_with_completion'])
                and not cases['descendant_propagation']['focused_without_completion']
                and cases['descendant_propagation']['native_total_nodes'] == cases['descendant_propagation']['completion_count'],
                'branching totals reconcile; propagation-only root has one native node but no completed event (zero credit)')
        require('restart', bool(restart['run_transitions']) and bool(restart['reused_numbers']) and restart['old_epoch_rejections'] > 0
                and restart['init_calls'] >= 2 and restart['exit_calls'] >= 2 and restart['native_runs'] >= 2
                and any(t['after'] > t['before'] >= 1 for t in restart['run_transitions'])
                and restart['completion_count'] == restart['native_total_nodes'],
                'cooperative native restart, counter transition, lifecycle hooks, reused numbers, old-key rejection')
        require('events', all(branch['events'].get(k, 0) > 0 for k in ('NODEBRANCHED', 'NODEDELETE', 'BESTSOLFOUND', 'DUALBOUNDIMPROVED')),
                'registered native completion/deletion/incumbent/dual-bound events')
        require('cleanup', all(c['subscriptions_after_free'] == 0 and c['plugin_models_released'] for c in cases.values()), 'explicit dropEvent on eventexit')
        require('interruption', stop['status'] == 'userinterrupt' and stop['legal_selections_after_stop'] > 0,
                'interruptSolve followed by required legal live selection')
        report['clock'] = _clock_evidence()
        require('monotonic_comparability', report['clock']['comparable'], 'five bounded parent/child monotonic ping-pongs')
        report['peak_rss_bytes'] = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * (1 if sys.platform == 'darwin' else 1024)
    except Exception as exc:
        report['errors'].append(f'{type(exc).__name__}: {exc}')
        if hasattr(exc, 'callback_fault'):
            report['callback_fault'] = exc.callback_fault
        if hasattr(exc, 'failed_case'):
            report['failed_case'] = exc.failed_case
        operations['native_discovery'] = {'status': 'blocked', 'evidence': report['errors'][-1]}
    for name in ('normal_enhancements', 'original_transformed_objectives', 'live_selection', 'ancestry',
                 'deletion', 'completion', 'restart', 'events', 'cleanup', 'interruption', 'monotonic_comparability'):
        operations.setdefault(name, {'status': 'missing', 'evidence': 'discovery did not reach this operation'})
    report['success'] = not report['errors'] and all(v['status'] == 'exercised' for v in operations.values())
    report['elapsed_ns'] = time.perf_counter_ns() - started
    report['cpu_ns'] = time.process_time_ns() - cpu_started
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_suffix(out.suffix + '.tmp')
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n')
    temporary.replace(out)
    return report
