import pytest

from ra.ledger import CreditLedger


def test_unused_allowance_returns_once():
    ledger = CreditLedger(total_units=10)
    ledger.reserve("lease", 4)
    ledger.spend("lease", 2)
    assert ledger.close("lease") == 2
    assert ledger.snapshot() == {"available": 8, "reserved": 0, "spent": 2}
    with pytest.raises(ValueError):
        ledger.close("lease")
    assert ledger.snapshot()["available"] == 8


def test_canceled_lineage_cannot_spend_or_reopen():
    ledger = CreditLedger(10)
    ledger.reserve("canceled", 4)
    ledger.close("canceled")
    before = ledger.snapshot()
    for action in (lambda: ledger.spend("canceled"),
                   lambda: ledger.reserve("canceled", 2)):
        with pytest.raises(ValueError):
            action()
        assert ledger.snapshot() == before


def test_split_merge_spawn_cancel_conserve_mass():
    ledger = CreditLedger(100)
    for cycle in range(10):
        parent, left, right, merged, spawned = [f"{cycle}:{s}" for s in
                                              ("parent", "left", "right", "merged", "spawned")]
        ledger.reserve(parent, 8)
        assert ledger.close(parent) == 8
        ledger.reserve(left, 3)
        ledger.reserve(right, 5)
        ledger.spend(right)
        assert ledger.close(left) + ledger.close(right) == 7
        ledger.reserve(merged, 7)
        assert ledger.close(merged) == 7
        ledger.reserve(spawned, 7)
        ledger.spend(spawned)
        assert ledger.close(spawned) == 6
        balance = ledger.snapshot()
        assert sum(balance.values()) == 100
        assert all(type(v) is int and v >= 0 for v in balance.values())
    assert ledger.snapshot() == {"available": 80, "reserved": 0, "spent": 20}


@pytest.mark.parametrize("value", [-1, 1.5, True, "10", None])
def test_budget_requires_nonnegative_integer(value):
    with pytest.raises(ValueError):
        CreditLedger(value)


@pytest.mark.parametrize("value", [-1, 1.5, True, "1", None, 11])
def test_invalid_allowances_leave_balances_unchanged(value):
    ledger = CreditLedger(10)
    before = ledger.snapshot()
    with pytest.raises(ValueError):
        ledger.reserve("lease", value)
    assert ledger.snapshot() == before
    ledger.reserve("lease", 4)
    before = ledger.snapshot()
    with pytest.raises(ValueError):
        ledger.spend("lease", value)
    assert ledger.snapshot() == before


def test_overdraft_duplicate_and_unknown_operations_are_atomic():
    ledger = CreditLedger(10)
    ledger.reserve("lease", 4)
    before = ledger.snapshot()
    for action in (lambda: ledger.reserve("lease", 1),
                   lambda: ledger.reserve("other", 7),
                   lambda: ledger.spend("lease", 5),
                   lambda: ledger.spend("missing"),
                   lambda: ledger.close("missing")):
        with pytest.raises(ValueError):
            action()
        assert ledger.snapshot() == before
    ledger.spend("lease", 4)
    assert ledger.close("lease") == 0
    assert ledger.snapshot() == {"available": 6, "reserved": 0, "spent": 4}


@pytest.mark.parametrize("lease_id", ["", None, 1, True])
def test_lease_ids_are_nonempty_strings(lease_id):
    ledger = CreditLedger(10)
    with pytest.raises(ValueError):
        ledger.reserve(lease_id, 1)
    assert ledger.snapshot() == {"available": 10, "reserved": 0, "spent": 0}


def test_zero_units_and_snapshot_do_not_create_credit():
    ledger = CreditLedger(0)
    ledger.reserve("empty", 0)
    ledger.spend("empty", 0)
    assert ledger.close("empty") == 0
    snapshot = ledger.snapshot()
    snapshot["available"] = 100
    assert ledger.snapshot() == {"available": 0, "reserved": 0, "spent": 0}
