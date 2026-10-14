"""Exact administrative allowances, separate from evidence and native work counts."""

from __future__ import annotations


def _units(value: int) -> None:
    if type(value) is not int or value < 0:
        raise ValueError("units must be a nonnegative integer")


class CreditLedger:
    """Reserve once per lineage, charge work, and return unused credit once.

    Closing also represents cancellation. IDs cannot be reused after closure;
    spawning a successor requires a fresh ID. Zero allowances are permitted.
    This class has no evidence, bound, estimate, or native stopping-limit state.
    """

    def __init__(self, total_units: int):
        _units(total_units)
        self._available = total_units
        self._spent = 0
        self._remaining: dict[str, int] = {}
        self._closed: set[str] = set()

    def reserve(self, lease_id: str, units: int) -> None:
        if not isinstance(lease_id, str) or not lease_id:
            raise ValueError("lease ID must be a nonempty string")
        _units(units)
        if lease_id in self._remaining or lease_id in self._closed:
            raise ValueError("lease ID has already been used")
        if units > self._available:
            raise ValueError("insufficient available credit")
        self._remaining[lease_id] = units
        self._available -= units

    def _allowance(self, lease_id: str) -> int:
        if not isinstance(lease_id, str) or lease_id not in self._remaining:
            raise ValueError("lease is unknown or closed")
        return self._remaining[lease_id]

    def spend(self, lease_id: str, units: int = 1) -> None:
        _units(units)
        remaining = self._allowance(lease_id)
        if units > remaining:
            raise ValueError("insufficient reserved credit")
        self._remaining[lease_id] -= units
        self._spent += units

    def close(self, lease_id: str) -> int:
        remaining = self._allowance(lease_id)
        del self._remaining[lease_id]
        self._closed.add(lease_id)
        self._available += remaining
        return remaining

    def snapshot(self) -> dict[str, int]:
        return {"available": self._available,
                "reserved": sum(self._remaining.values()), "spent": self._spent}


class TimeLedger:
    """A monotonic stack of exclusive categories; diagnostics never add elapsed.

    The most deeply nested nondiagnostic scope owns time. Unscoped time is
    residual. summary is a snapshot and does not close live scopes.
    """
    categories = ('startup', 'native', 'administration', 'observation', 'finalization', 'residual')

    def __init__(self, start_ns: int = 0):
        _units(start_ns)
        self._last = start_ns
        self._stack: list[tuple[str, int]] = []
        self._totals = dict.fromkeys(self.categories, 0)
        self.diagnostics: dict[str, int] = {}

    def _check(self, now_ns):
        _units(now_ns)
        if now_ns < self._last:
            raise ValueError('time must be monotonic')

    def _category(self):
        return next((name for name, _ in reversed(self._stack)
                     if not name.startswith('diagnostic:')), 'residual')

    def _tick(self, now_ns):
        self._check(now_ns)
        self._totals[self._category()] += now_ns - self._last
        self._last = now_ns

    def enter(self, category: str, now_ns: int) -> None:
        if category not in self.categories and not (isinstance(category, str)
                and category.startswith('diagnostic:') and category[11:]):
            raise ValueError('unknown timing category')
        self._tick(now_ns)
        self._stack.append((category, now_ns))

    def leave(self, now_ns: int) -> None:
        if not self._stack:
            raise ValueError('no timing scope to leave')
        self._tick(now_ns)
        category, start = self._stack.pop()
        if category.startswith('diagnostic:'):
            name = category[11:]
            self.diagnostics[name] = self.diagnostics.get(name, 0) + now_ns - start

    def summary(self, end_ns: int) -> dict[str, int]:
        self._check(end_ns)
        result = dict(self._totals)
        result[self._category()] += end_ns - self._last
        return result


def timed(category):
    """Time a callback/observer method when its owner has an attached ledger."""
    from functools import wraps
    import time
    def decorate(method):
        @wraps(method)
        def call(owner, *args, **kwargs):
            ledger = getattr(getattr(owner, 'backend', owner), 'time_ledger', None)
            if ledger is None:
                return method(owner, *args, **kwargs)
            ledger.enter(getattr(owner, 'timing_category', 'administration') if category == 'callback' else category,
                         time.perf_counter_ns())
            try:
                return method(owner, *args, **kwargs)
            finally:
                ledger.leave(time.perf_counter_ns())
        return call
    return decorate
