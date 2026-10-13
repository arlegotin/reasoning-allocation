import math

import pytest
from scipy.sparse import csr_matrix

from ra.exact import CoverValidationError, normalized_utility, verify_cover
from ra.types import CoverInstance


def cover(rows=((0, 1), (1, 2)), costs=(1, 2, 1)):
    rr = [i for i, row in enumerate(rows) for _ in row]
    cc = [j for row in rows for j in row]
    a = csr_matrix(([1] * len(cc), (rr, cc)), shape=(len(rows), len(costs)))
    return CoverInstance('tiny', 'tiny-template', 'tiny-cell', a, costs, {'generator_version': 'fixture-v1'})


def test_original_integer_objective():
    result = verify_cover(cover(), (1.0, 0.0, 1.0), 1e-6)
    assert result.binary == (1, 0, 1)
    assert result.objective == 2
    assert verify_cover(cover(), (1, 1, 1), 1e-6).objective == 4
    assert len(result.content_hash) == 64


@pytest.mark.parametrize('values', [(0.5, 0, 1), (0, 0, 0), (1, 0), (math.nan, 0, 1), (math.inf, 0, 1), (2, 0, 1)])
def test_invalid_assignments_reject(values):
    with pytest.raises(CoverValidationError):
        verify_cover(cover(), values, 1e-6)


def test_only_locked_tolerance_rounds():
    assert verify_cover(cover(), (1 - 5e-7, -5e-7, 1 + 5e-7), 1e-6).objective == 2
    with pytest.raises(CoverValidationError):
        verify_cover(cover(), (1 - 2e-6, 0, 1), 1e-6)


@pytest.mark.parametrize('tolerance', [-1, .5, math.nan, math.inf, True])
def test_invalid_integrality_tolerance_rejects(tolerance):
    with pytest.raises(CoverValidationError):
        verify_cover(cover(), (1, 0, 1), tolerance)


def test_accumulation_above_uint8_and_int64():
    assert verify_cover(cover((tuple(range(256)),), (2,) * 256), (1,) * 256, 1e-6).objective == 512
    huge = 2**63
    assert verify_cover(cover(((0, 1),), (huge, huge + 1)), (1, 1), 1e-6).objective == 2 * huge + 1


@pytest.mark.parametrize('rows,costs', [(((0,), ()), (1,)), (((0,),), (0,)), (((0,),), (1.5,))])
def test_invalid_original_problem_rejects(rows, costs):
    with pytest.raises(CoverValidationError):
        verify_cover(cover(rows, costs), (1,) * len(costs), 1e-6)


def test_duplicate_and_nonbinary_sparse_incidence_reject():
    a = csr_matrix(([1, 1], [0, 0], [0, 2]), shape=(1, 1))
    instance = CoverInstance('i', 't', 'c', a, (1,), {})
    with pytest.raises(CoverValidationError):
        verify_cover(instance, (1,), 1e-6)
    a.data[:] = 2
    with pytest.raises(CoverValidationError):
        verify_cover(instance, (1,), 1e-6)


def test_positive_affine_utility_and_alarm_without_clipping():
    assert normalized_utility(6, 2, 10, 0) == pytest.approx(.6)
    assert normalized_utility(25, 13, 37, 7) == pytest.approx(.6)
    assert normalized_utility(2, 2 + 1e-8, 4, 0, tolerance=1e-6) > 1
    with pytest.raises(CoverValidationError):
        normalized_utility(2, 3, 4, 0)
    with pytest.raises(CoverValidationError):
        normalized_utility(2, 1, 0, 0)


def test_corrupt_noninteger_csr_indices_are_not_truncated():
    import numpy as np
    instance = cover(((0,),), (1,))
    instance.incidence.indices = np.array([.5])
    with pytest.raises(CoverValidationError):
        verify_cover(instance, (1,), 1e-6)
