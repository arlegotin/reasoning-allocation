"""One original-space verifier/cache for native and Python-selected requests."""
from __future__ import annotations

import math
import time
from typing import Callable, Sequence

from ra.exact import CoverValidationError, canonical_cover, normalized_utility, verify_cover
from ra.ledger import timed
from ra.types import CoverInstance, ProgressRecord, VerifiedAssignment


class NumericalAlarm(ValueError):
    """Original feasibility/objective/bound failed the locked numerical contract."""


class Observer:
    def __init__(self, instance: CoverInstance, *, request_id: str,
                 integrality_tolerance: float = 1e-6, bound_tolerance: float = 1e-6,
                 objective_scale: int = 1, objective_offset: int = 0,
                 publish: Callable[[ProgressRecord], None] | None = None):
        canonical_cover(instance)
        if (type(objective_scale) is not int or objective_scale <= 0 or type(objective_offset) is not int
                or isinstance(integrality_tolerance, bool) or not math.isfinite(integrality_tolerance)
                or not 0 <= integrality_tolerance < .5 or isinstance(bound_tolerance, bool)
                or not math.isfinite(bound_tolerance) or bound_tolerance < 0):
            raise ValueError('invalid observer numerical settings')
        self.instance, self.request_id = instance, request_id
        self.integrality_tolerance, self.bound_tolerance = integrality_tolerance, bound_tolerance
        self.scale, self.offset = objective_scale, objective_offset
        self.p0 = objective_scale * sum(instance.costs) + objective_offset
        self.d0 = float(objective_offset)
        self.primal: int | None = None
        self.dual = self.d0
        self.incumbent_hash: str | None = None
        self.assignments: dict[str, VerifiedAssignment] = {}
        self.records: list[ProgressRecord] = []
        self.publish = publish
        self.last_native_dual: float | None = None
        self._last_native_objective: float | None = None
        self.intervals: list[tuple[int, int, str]] = []

    def _check(self, primal, dual):
        try:
            return normalized_utility(primal, dual, self.p0, self.d0, tolerance=self.bound_tolerance)
        except CoverValidationError as exc:
            raise NumericalAlarm(str(exc)) from None

    def _emit(self, event_ns: int) -> ProgressRecord:
        if type(event_ns) is not int or event_ns < 0 or self.records and event_ns < self.records[-1].child_ns:
            raise ValueError('observer events must have ordered integer timestamps')
        record = ProgressRecord(self.request_id, len(self.records) + 1, event_ns, None,
                                self.primal, self.dual, self.incumbent_hash, self.primal is not None)
        self.records.append(record)
        if self.publish is not None:
            self.publish(record)
        return record

    def validate_incumbent(self, values: Sequence[float], event_ns: int) -> ProgressRecord:
        try:
            assignment = verify_cover(self.instance, values, self.integrality_tolerance)
        except CoverValidationError as exc:
            raise NumericalAlarm(str(exc)) from None
        primal = self.scale * assignment.objective + self.offset
        self._check(primal, self.dual)
        if self.primal is None or primal < self.primal:
            self.assignments[assignment.content_hash] = assignment
            self.incumbent_hash, self.primal = assignment.content_hash, primal
        return self._emit(event_ns)

    def observe_dual(self, bound_original: float, event_ns: int) -> ProgressRecord:
        if isinstance(bound_original, bool) or not math.isfinite(bound_original):
            raise NumericalAlarm('nonfinite original dual')
        if self.primal is not None:
            self._check(self.primal, bound_original)
        self.last_native_dual = bound_original
        self.dual = max(self.dual, bound_original)  # Retain the proven structural/previous bound.
        return self._emit(event_ns)

    def available_local(self) -> tuple[float, float, float]:
        if self.primal is None:
            return math.inf, self.dual, 0.
        return float(self.primal), self.dual, self._check(self.primal, self.dual)

    @timed('observation')
    def poll(self, model, variable_names: Sequence[str], event_ns: int) -> None:
        """Event + terminal fallback, using only call-local original native wrappers.

        An unchanged native objective needs no repeated variable scan or verification:
        the already verified original assignment remains the deliverable at that cost.
        """
        started = time.perf_counter_ns()
        try:
            sol = model.getBestSol()
            if sol is not None:
                native = float(model.getSolObjVal(sol, original=True))
                if not math.isfinite(native):
                    raise NumericalAlarm('nonfinite original primal')
                if native != self._last_native_objective:
                    variables = {v.name: v for v in model.getVars(transformed=False)}
                    if set(variables) != set(variable_names):
                        raise NumericalAlarm('original variable schema mismatch')
                    values = tuple(float(model.getSolVal(sol, variables[name])) for name in variable_names)
                    # Check before publishing; a lying native objective never yields an accepted record.
                    try:
                        assignment = verify_cover(self.instance, values, self.integrality_tolerance)
                    except CoverValidationError as exc:
                        raise NumericalAlarm(str(exc)) from None
                    expected = self.scale * assignment.objective + self.offset
                    if abs(native - expected) > self.bound_tolerance:
                        raise NumericalAlarm('original objective mismatch')
                    self.validate_incumbent(values, event_ns)
                    self._last_native_objective = native
            dual = float(model.getDualbound())
            if model.isInfinity(abs(dual)):
                if dual > 0:
                    raise NumericalAlarm('infinite positive dual for feasible cover')
                dual = self.d0
            if not math.isfinite(dual):
                raise NumericalAlarm('nonfinite original dual')
            self.last_native_dual = dual
            if dual > self.dual:
                self.observe_dual(dual, event_ns)
        finally:
            self.intervals.append((started, time.perf_counter_ns(), 'observation'))
