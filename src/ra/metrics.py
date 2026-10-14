"""Authoritative receipt-gated progress; child-local values are never labels."""
from __future__ import annotations

import math
from typing import Sequence

from ra.exact import normalized_utility
from ra.types import Attempt, AvailableProgress, ProgressRecord


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


def log_budget_weights(deadlines: Sequence[float]) -> list[float]:
    """Normalized trapezoidal integration on strictly increasing log deadlines."""
    if (len(deadlines) < 2 or any(isinstance(x, bool) or not isinstance(x, (int, float))
            or not math.isfinite(x) or x <= 0 for x in deadlines)
            or any(a >= b for a, b in zip(deadlines, deadlines[1:]))):
        raise ValueError('at least two positive finite increasing deadlines required')
    points = [math.log(x) for x in deadlines]
    span = points[-1] - points[0]
    widths = [b-a for a,b in zip(points, points[1:])]
    return [widths[0]/(2*span), *[(a+b)/(2*span) for a,b in zip(widths,widths[1:])], widths[-1]/(2*span)]


def summarize_attempts(attempts: Sequence['Attempt'], protocol: dict[str, object]) -> list[dict[str, object]]:
    """One receipt-reconstructed cold endpoint per row; frontier repeats on its budgets.

    Callers authenticate/reconstruct Attempts first. Queue labels identify repeats
    and genuine fits; solver seeds and leases never become independent units.
    """
    from collections import defaultdict
    from ra.freeze import read
    from pathlib import Path
    deadlines, weights = protocol['deadlines_ns'], protocol['weights']
    if len(weights) != len(deadlines) or not math.isclose(sum(weights), 1.):
        raise ValueError('invalid frontier weights')
    queue = read(Path(protocol['queue']['path'])) if 'queue' in protocol else []
    metadata = {r['request_id']:r for r in queue}
    names = {v['name']:k for k,v in protocol['physical_methods'].items()}
    groups, rows, seen = defaultdict(list), [], set()
    native = protocol['planning']['native_methods']
    for a in attempts:
        r, available = a.request, a.available
        q = metadata.get(a.request_id)
        if queue and q is None: raise ValueError('attempt absent from frozen queue')
        method = q['method'] if q else names[r.method]
        fit = q['fit_id'] if q else ('shared' if method in native else protocol['fit_ids'][0])
        repeat = q['repeat'] if q else r.solver_seed
        key = (a.template_id, method, fit, repeat)
        identity = (*key, r.budget_ns)
        if identity in seen: raise ValueError('duplicate endpoint')
        if r.budget_ns not in deadlines: raise ValueError('unregistered budget')
        seen.add(identity)
        primal, dual = available.primal_original, available.dual_original
        gap = primal-dual if primal is not None else None
        alarm = a.quarantined or a.status == 'numerical_alarm'
        if available.assignment_available:
            rebuilt = normalized_utility(primal,dual,r.p0,tolerance=r.bound_tolerance,anchor_dual=0)
            if not math.isclose(rebuilt,available.utility,abs_tol=1e-12):
                raise ValueError('available utility mismatch')
        elif available.utility != 0 or primal is not None:
            raise ValueError('unavailable assignment has utility')
        row = dict(template_id=a.template_id,cell_id=a.cell_id,method=method,fit_id=fit,repeat=repeat,
            request_id=a.request_id,attempt_id=a.attempt_id,budget_ns=r.budget_ns,deadline_ns=r.deadline_ns,
            population_cell_weight=protocol['planning']['cells'][a.cell_id],
            family=(a.lineage or {}).get('cell',a.lineage or {}).get('family'),status=str(a.status),utility=available.utility,
            assignment_available=available.assignment_available,primal=primal,dual=dual,raw_gap=gap,
            plot_gap=max(0.,gap) if gap is not None else None,
            relative_gap=gap/max(1.,abs(primal)) if gap is not None else None,
            normalized_primal=primal/r.p0 if primal is not None else None,normalized_dual=dual/r.p0,
            solved=gap is not None and abs(gap)<=r.bound_tolerance,correctness_alarm=alarm,
            fault=a.status not in ('complete','deadline'),duration_censored=a.duration_censored,
            overshoot_ns=a.overshoot_ns,initial_primal=r.p0)
        row.update({'resource_'+k:v for k,v in a.resources.items() if isinstance(v,(int,float,bool)) or v is None})
        row.update({'timestamp_'+k:v for k,v in a.timestamps.items()})
        groups[key].append(row); rows.append(row)
    for group in groups.values():
        if sorted(r['budget_ns'] for r in group)!=deadlines: raise ValueError('incomplete frontier budgets')
        frontier = sum(w*next(r['utility'] for r in group if r['budget_ns']==b) for b,w in zip(deadlines,weights))
        for row in group: row['frontier']=frontier
    return rows
