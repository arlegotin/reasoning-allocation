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
