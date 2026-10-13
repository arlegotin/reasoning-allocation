"""Bounded subtree continuation with exact, per-grant administrative credit."""
from __future__ import annotations

import time
from typing import Callable, Mapping, Sequence

from ra.ledger import CreditLedger
from ra.types import Allocation, LeaseOutcome, NodeKey, NodeRecord


class LeaseController:
    """Keep primitive ancestry only; ``None`` requests a rebid, not a native node.

    ``parents`` is the adapter's live primitive ancestry mapping. Every grant gets
    a separate ledger: this allowance never imposes a global search stop budget.
    ``clock`` shares the adapter's monotonic nanosecond domain. Native callbacks
    own request_stop and resolution; no wrappers enter this controller.
    """
    def __init__(self, parents: Mapping[NodeKey, NodeKey | None], *,
                 deadline_ns: int | None = None, request_stop: Callable[[], None] | None = None,
                 clock: Callable[[], int] = time.perf_counter_ns):
        self.parents = parents
        self.deadline_ns = deadline_ns
        self.request_stop = request_stop
        self.clock = clock
        self._allocation: Allocation | None = None
        self._outcome: LeaseOutcome | None = None
        self.ledger: CreditLedger | None = None

    @property
    def active(self) -> bool:
        return self._allocation is not None and self._reason is None

    @property
    def pending(self) -> bool:
        return self._allocation is not None and self._outcome is None

    def begin(self, allocation: Allocation, decision_start_ns: int) -> None:
        if self.pending:
            raise RuntimeError('finish the previous lease before beginning another')
        if type(allocation.node_limit) is not int or allocation.node_limit <= 0:
            raise ValueError('lease length must be a positive integer')
        self._allocation, self._outcome = allocation, None
        self._entry_ns, self._dispatch_ns = decision_start_ns, None
        self._reason = None
        self._root_selected = False
        self._selected: set[NodeKey] = set()
        self._completed: set[NodeKey] = set()
        self._post_deadline: set[NodeKey] = set()
        self._unused = self._continuation_ns = 0
        self.ledger = CreditLedger(allocation.node_limit)
        self.ledger.reserve('grant', allocation.node_limit)

    def _end(self, reason: str) -> None:
        if self.active:
            self._reason = reason
            self._unused = self.ledger.close('grant')

    def cancel(self, reason: str) -> None:
        self._end(reason)

    def _on_deleted(self, key: NodeKey) -> None:
        if not self.active:
            return
        ancestor = self._allocation.root
        seen = set()
        while ancestor is not None:
            if ancestor == key:
                self.cancel('ancestor_deleted')
                return
            if ancestor in seen or ancestor not in self.parents:
                raise ValueError('missing or cyclic primitive ancestor')
            seen.add(ancestor)
            ancestor = self.parents[ancestor]

    def _charge_continuation_scan(self, duration_ns: int) -> None:
        if self.pending:
            self._continuation_ns += duration_ns

    def _deadline(self, now_ns: int) -> bool:
        if self.deadline_ns is None or now_ns < self.deadline_ns:
            return False
        self._end('deadline')
        if self.request_stop is not None:
            self.request_stop()
        return True

    def _descendant(self, key: NodeKey) -> bool:
        root = self._allocation.root
        seen = set()
        while key is not None:
            if key == root:
                return True
            if key in seen or key not in self.parents:
                raise ValueError('missing or cyclic primitive ancestor')
            seen.add(key)
            key = self.parents[key]
        return False

    def on_completed(self, key: NodeKey) -> None:
        # Only dispatch-owned completions spend this grant. Administrative rebids,
        # root setup before first selection, and native counter deltas do not.
        if not self.pending or key not in self._selected or key in self._completed:
            return
        if self.active and self.deadline_ns is not None:
            self._deadline(self.clock())
        if self._reason == 'deadline':
            self._post_deadline.add(key)
            return
        if not self.active:
            return
        self._completed.add(key)
        self.ledger.spend('grant')
        if len(self._completed) == self._allocation.node_limit:
            self._end('node_limit')

    def next_node(self, frontier: Sequence[NodeRecord], now_ns: int) -> NodeKey | None:
        if not self.active:
            return None
        continuing = self._dispatch_ns is not None
        started = self.clock()
        selected = False
        try:
            if self._deadline(now_ns):
                return None
            root = self._allocation.root
            if any(node.key.epoch != root.epoch for node in frontier):
                self._end('restart')
                return None
            if not self._root_selected:
                candidate = next((node for node in frontier if node.key == root), None)
            elif root not in self._completed:
                candidate = next((node for node in frontier if node.key == root), None)
            else:
                descendants = [node for node in frontier if self._descendant(node.key)]
                candidate = min(descendants, key=lambda n: (-n.depth, n.native_estimate,
                                                            n.native_lower_bound, n.key.number), default=None)
            if candidate is None:
                self._end('exhaustion')
                return None
            self._root_selected = True
            self._selected.add(candidate.key)
            selected = True
            return candidate.key
        finally:
            duration_ns = self.clock() - started
            if continuing and selected:
                self._continuation_ns += duration_ns

    def mark_dispatch(self, dispatch_ns: int) -> None:
        if self.pending and self._dispatch_ns is None:
            self._dispatch_ns = dispatch_ns
        if self.active:
            self._deadline(dispatch_ns)

    def finish(self, end_ns: int, reason: str) -> LeaseOutcome:
        """Close at next rebid entry or the caller's terminal boundary.

        Node-limit/cancellation events close credit immediately, but body time
        continues through this supplied boundary. It includes native work after
        the last completion and all continuation callbacks. ``continuation_ns``
        separately measures successful continuation scans, within that body.
        """
        if self._allocation is None:
            raise RuntimeError('no lease to finish')
        if self._outcome is None:
            self._end(reason)
            self._outcome = LeaseOutcome(self._allocation.root, self._allocation.node_limit,
                len(self._completed), self._entry_ns, self._dispatch_ns, end_ns, self._reason,
                self._reason in ('node_limit', 'exhaustion', 'terminal'),
                self._reason not in ('node_limit', 'exhaustion', 'terminal'),
                self._unused, 0 if self._dispatch_ns is None else end_ns-self._dispatch_ns,
                self._continuation_ns, len(self._post_deadline))
        return self._outcome
