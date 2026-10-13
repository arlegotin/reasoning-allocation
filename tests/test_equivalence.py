from dataclasses import FrozenInstanceError

import pytest

from ra.checks import EvidenceRecord, coupled_administration, evidence_clone_diagnostic


@pytest.mark.parametrize("seed", [0, 1, 42, 511])
def test_queue_and_population_share_process_mass_and_rng(seed):
    result = coupled_administration(seed)
    assert result["matched_decisions"] == 20
    assert result["operations"] == {"split": 10, "merge": 10, "cancel": 10, "spawn": 10}
    assert result["balances"] == {"available": 800, "reserved": 180, "spent": 20}
    assert result["canceled_zero_mass_records"] == 40
    assert result["evidence_hashes_before"] == result["evidence_hashes_after"]
    assert len(result["evidence_hashes_before"]) == 2


def test_evidence_clone_does_not_repeat_observation_or_change_native_values():
    result = evidence_clone_diagnostic()
    assert result["evidence_id"] == "e1"
    assert result["administrative_copies"] == 2
    assert result["posterior"] == 0.8
    assert result["native_bound"] == 2.0
    assert result["native_estimate"] == 3.0
    assert result["before_hash"] == result["after_hash"]
    assert result["balances"] == {"available": 8, "reserved": 0, "spent": 2}


def test_evidence_record_is_immutable():
    record = EvidenceRecord("e1", 0.8, 2.0, 3.0)
    with pytest.raises(FrozenInstanceError):
        record.posterior = 0.941176
