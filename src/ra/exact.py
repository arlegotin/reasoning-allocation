"""Independent original-space binary cover checks using Python integer sums.

Enumeration is deliberately explicit and exponential. Callers must measure an
affordable tiny scale; generation and the CLI never enumerate workloads.
"""
from __future__ import annotations

import hashlib
import json
import math
from numbers import Integral, Real
from typing import Sequence

from ra.types import CoverInstance, VerifiedAssignment


class CoverValidationError(ValueError):
    """Invalid original cover, assignment, tolerance, or progress references."""


def canonical_cover(instance: CoverInstance) -> dict[str, object]:
    """Check raw CSR before sorting: coalescing duplicates would hide invalid input."""
    a = instance.incidence
    if getattr(a, 'format', None) != 'csr' or len(a.shape) != 2:
        raise CoverValidationError('original incidence must be CSR')
    m, n = a.shape
    if m <= 0 or n <= 0 or len(instance.costs) != n:
        raise CoverValidationError('cover shape and costs must match and be nonempty')
    if any(isinstance(c, bool) or not isinstance(c, Integral) or c <= 0 for c in instance.costs):
        raise CoverValidationError('cover costs must be positive integers')
    if (any(not isinstance(v, Integral) for v in (*a.indptr, *a.indices)) or
            len(a.indptr) != m + 1 or int(a.indptr[0]) != 0 or
            int(a.indptr[-1]) != len(a.indices) or len(a.data) != len(a.indices)):
        raise CoverValidationError('malformed CSR offsets')
    rows = []
    for r in range(m):
        start, end = int(a.indptr[r]), int(a.indptr[r + 1])
        if not 0 <= start < end <= len(a.indices):
            raise CoverValidationError('cover rows must be nonempty with valid offsets')
        row = [int(j) for j in a.indices[start:end]]
        if len(set(row)) != len(row) or any(not 0 <= j < n for j in row):
            raise CoverValidationError('duplicate or out-of-range incidence')
        if any(v != 1 for v in a.data[start:end]):
            raise CoverValidationError('incidence must be binary with no stored zeros')
        rows.append(sorted(row))
    return {'shape': [m, n], 'rows': rows, 'costs': [int(c) for c in instance.costs]}


def verify_cover(instance: CoverInstance, values: Sequence[float], integrality_tolerance: float) -> VerifiedAssignment:
    problem = canonical_cover(instance)
    if (isinstance(integrality_tolerance, bool) or not isinstance(integrality_tolerance, Real) or
            not math.isfinite(integrality_tolerance) or not 0 <= integrality_tolerance < .5):
        raise CoverValidationError('integrality tolerance must be finite and in [0, .5)')
    if len(values) != len(instance.costs):
        raise CoverValidationError('assignment length must match original columns')
    binary = []
    for v in values:
        if not isinstance(v, Real) or not math.isfinite(v):
            raise CoverValidationError('assignment must be finite real values')
        rounded = round(v)
        if rounded not in (0, 1) or abs(v - rounded) > integrality_tolerance:
            raise CoverValidationError('assignment is outside locked integrality tolerance')
        binary.append(int(rounded))
    if any(sum(binary[j] for j in row) < 1 for row in problem['rows']):
        raise CoverValidationError('assignment does not cover every original row')
    objective = sum(int(c) * x for c, x in zip(instance.costs, binary))
    payload = json.dumps({'cover': problem, 'binary': binary, 'objective': objective}, sort_keys=True, separators=(',', ':'))
    return VerifiedAssignment(tuple(binary), objective, hashlib.sha256(payload.encode()).hexdigest())


def enumerate_cover(instance: CoverInstance) -> VerifiedAssignment:
    problem = canonical_cover(instance)
    n = len(instance.costs)
    row_masks = [sum(1 << j for j in row) for row in problem['rows']]
    best_mask, best_cost = (1 << n) - 1, sum(int(c) for c in instance.costs)
    # Every binary assignment is visited; native relaxations/solver status play no part.
    for mask in range(1 << n):
        if all(mask & row for row in row_masks):
            cost = sum(int(c) for j, c in enumerate(instance.costs) if mask & (1 << j))
            if cost < best_cost:
                best_mask, best_cost = mask, cost
    return verify_cover(instance, tuple((best_mask >> j) & 1 for j in range(n)), 0)


def normalized_utility(primal: float, dual: float, anchor_primal: float, anchor_dual: float,
                       *, tolerance: float = 1e-6) -> float:
    values = (primal, dual, anchor_primal, anchor_dual, tolerance)
    if any(isinstance(v, bool) or not isinstance(v, Real) or not math.isfinite(v) for v in values):
        raise CoverValidationError('utility references and tolerance must be finite real values')
    if tolerance < 0 or anchor_primal <= anchor_dual:
        raise CoverValidationError('utility requires nonnegative tolerance and positive anchor denominator')
    if dual > primal + tolerance:
        raise CoverValidationError('dual bound exceeds checked primal')
    return 1 - (primal - dual) / (anchor_primal - anchor_dual)
