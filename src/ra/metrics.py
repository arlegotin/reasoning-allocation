"""Authoritative receipt-gated progress; child-local values are never labels."""
from __future__ import annotations

import math
from typing import Sequence

from ra.exact import normalized_utility
from ra.types import AvailableProgress, ProgressRecord


def utility(p: float, d: float, p0: int, d0: float = 0.0) -> float:
    return normalized_utility(p, d, p0, d0)


def validate_clock_alignment(samples: Sequence[tuple[int, int, int]]) -> bool:
    """Every child sample must lie inside its causal parent ping/receipt bracket.

    This tests shared monotonic comparability, not synchronization precision.
    Bracket widths remain evidence; failure requires translation before labels.
    """
    return bool(samples) and all(all(type(v) is int and v >= 0 for v in sample)
                                 and len(sample) == 3 and sample[0] <= sample[1] <= sample[2]
                                 for sample in samples)


class ProgressStream:
    """Incremental receipt validation shared with offline replay (linear work)."""
    def __init__(self, deadline_ns: int, p0: int, *, clock_aligned: bool = True,
                 bound_tolerance: float = 1e-6):
        if not clock_aligned:
            raise ValueError('clock alignment unverified: label reconstruction blocked')
        if type(deadline_ns) is not int or deadline_ns < 0:
            raise ValueError('deadline must be nonnegative integer nanoseconds')
        normalized_utility(p0, 0, p0, 0, tolerance=bound_tolerance)
        self.deadline_ns, self.p0, self.bound_tolerance = deadline_ns, p0, bound_tolerance
        self.available = AvailableProgress(False, 0., None, 0., None)
        self.previous = None
        self.identities = {}

    def accept(self, record: ProgressRecord) -> AvailableProgress:
        previous = self.previous
        if (type(record.schema_version) is not int or record.schema_version != 1
                or type(record.sequence) is not int or record.sequence < 1
                or type(record.child_ns) is not int or record.child_ns < 0
                or type(record.receipt_ns) is not int or record.receipt_ns < record.child_ns
                or not record.request_id or type(record.assignment_available) is not bool
                or isinstance(record.dual_original, bool) or not math.isfinite(record.dual_original)):
            raise ValueError('invalid progress identity/timestamp/value')
        if previous is not None and (record.request_id != previous.request_id
                or record.sequence != previous.sequence + 1 or record.child_ns < previous.child_ns
                or record.receipt_ns < previous.receipt_ns):
            raise ValueError('duplicate/out-of-order or mixed-request progress')
        if previous is None and record.sequence != 1:
            raise ValueError('progress must start at sequence one')
        if record.assignment_available:
            if type(record.primal_original) is not int or record.primal_original <= 0 or not record.incumbent_hash:
                raise ValueError('available progress requires original objective and assignment identity')
            objective = self.identities.get(record.incumbent_hash, record.primal_original)
            if objective != record.primal_original:
                raise ValueError('assignment identity reused with different objective')
            value = normalized_utility(record.primal_original, record.dual_original, self.p0, 0,
                                       tolerance=self.bound_tolerance)
        else:
            if record.primal_original is not None or record.incumbent_hash is not None:
                raise ValueError('unavailable progress cannot name an incumbent')
            value = 0.
        if previous is not None and (record.dual_original < previous.dual_original or
                previous.assignment_available and (not record.assignment_available or
                    record.primal_original > previous.primal_original)):
            raise ValueError('validated progress regressed')
        if record.incumbent_hash is not None:
            self.identities[record.incumbent_hash] = record.primal_original
        if record.receipt_ns <= self.deadline_ns:
            self.available = AvailableProgress(record.assignment_available, value, record.primal_original,
                                               record.dual_original, record.incumbent_hash, record.sequence)
        self.previous = record
        return self.available


def progress_at(records: Sequence[ProgressRecord], deadline_ns: int, p0: int,
                *, clock_aligned: bool = True, bound_tolerance: float = 1e-6) -> AvailableProgress:
    stream = ProgressStream(deadline_ns, p0, clock_aligned=clock_aligned, bound_tolerance=bound_tolerance)
    for record in records:
        stream.accept(record)
    return stream.available
