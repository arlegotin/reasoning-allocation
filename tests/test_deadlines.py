"""Receipt time, not a solver timestamp, defines deliverable progress."""
from dataclasses import replace

import pytest

from ra.metrics import progress_at, utility, validate_clock_alignment
from ra.types import ProgressRecord


def record(sequence=1, child_ns=80, receipt_ns=100, primal=10, dual=0, identity='a'):
    return ProgressRecord(request_id='request', sequence=sequence, child_ns=child_ns,
                          receipt_ns=receipt_ns, primal_original=primal, dual_original=dual,
                          incumbent_hash=identity, assignment_available=primal is not None)


def test_late_receipt_cannot_publish_an_anchor():
    late = record(receipt_ns=101)
    assert late.child_ns == 80
    result = progress_at([late], deadline_ns=100, p0=10)
    assert result.assignment_available is False
    assert result.utility == 0.0
    assert result.incumbent_hash is None


def test_exact_receipt_boundary_and_post_deadline_improvement():
    anchor = record()
    improved = record(2, 90, 101, 8, 2, 'b')
    assert progress_at([anchor, improved], 100, 10).primal_original == 10
    assert progress_at([anchor, replace(improved, receipt_ns=100)], 100, 10).utility == pytest.approx(.4)
    assert progress_at([], 100, 10).utility == 0


@pytest.mark.parametrize('records', [
    [record(), record()],
    [record(2), record(1)],
    [record(), record(2, 79, 101)],
    [record(), record(2, 90, 99)],
    [record(), replace(record(2, 90, 101), request_id='other')],
    [replace(record(), receipt_ns=None)],
    [record(), record(2, 90, 101, 9, 0, 'a')],
])
def test_corrupt_sequence_identity_or_timing_rejects_even_late_data(records):
    with pytest.raises(ValueError):
        progress_at(records, 100, 10)


def test_unavailable_dual_is_not_an_assignment():
    result = progress_at([record(primal=None, dual=2, identity=None)], 100, 10)
    assert not result.assignment_available
    assert result.utility == 0


def test_utility_affine_invariance_and_raw_tolerance():
    assert utility(8, 2, 10) == pytest.approx(.4)
    assert utility(29, 11, 35, 5) == pytest.approx(.4)
    assert utility(8, 8 + 1e-7, 10) > 1
    with pytest.raises(ValueError):
        utility(8, 9, 10)


def test_clock_alignment_must_be_measured_and_blocks_labels():
    assert validate_clock_alignment([(10, 12, 15), (20, 22, 26), (30, 33, 35)])
    assert not validate_clock_alignment([(10, 1000, 15)])
    assert not validate_clock_alignment([])
    with pytest.raises(ValueError, match='clock'):
        progress_at([record()], 100, 10, clock_aligned=False)
