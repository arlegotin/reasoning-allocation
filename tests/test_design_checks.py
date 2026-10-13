import json
import platform
from pathlib import Path
import subprocess
import sys

import pytest

from ra.checks import anti_lease, run_design_checks
from ra.cli import main


@pytest.fixture(scope="module")
def checked(tmp_path_factory):
    out = tmp_path_factory.mktemp("analytical")
    return out, run_design_checks(out)


def assert_reference_results(result):
    assert result["queue_population"] == {"seeds": 512, "matched_decisions": 102400,
                                           "budget_and_evidence_checks": "passed"}
    assert result["delayed_reward"] == {"greedy_terminal_utility": 0.6,
                                        "optimal_terminal_utility": 1.0, "optimal_path": "BB"}
    assert result["bayes_duplicate"]["single_observation"] == pytest.approx(0.8)
    assert result["bayes_duplicate"]["incorrect_double_counting"] == pytest.approx(0.9411764705882353)
    assert result["illustrative_overhead"]["time_ratio_lease_1"] == pytest.approx(1.12)
    assert result["illustrative_overhead"]["time_ratio_lease_8"] == pytest.approx(0.84)


def test_appendix_a_expected_results(checked):
    _, result = checked
    assert_reference_results(result["appendix_a"])


def test_long_lease_can_lose():
    result = anti_lease()
    assert result["deadline_steps"] == 2
    assert result["a_steps_to_payoff"] == 1
    assert result["b_steps_to_payoff"] == 3
    assert result["long_lease_path"] == "BB"
    assert result["long_lease_utility"] == 0.0
    assert result["one_step_path"] == "AB"
    assert result["one_step_utility"] == 1.0


def test_report_records_measured_scope_environment_resources_and_persists(checked):
    out, report = checked
    assert report["success"] is True
    assert report["kind"] == "analytical"
    assert report["native_checks_executed"] is False
    assert report["appendix_a"]["environment"] == {
        "system": platform.system(), "machine": platform.machine(), "python": sys.version.split()[0]}
    assert report["resources"]["elapsed_ns"] > 0
    assert report["resources"]["process_cpu_ns"] > 0
    assert report["resources"]["process_peak_rss_bytes"] > 0
    assert len(report["reference_sha256"]) == 64
    assert json.loads((out / "design.json").read_text()) == report


def test_reference_script_independently_executes(tmp_path):
    script = Path(__file__).resolve().parents[1] / "checks" / "validate_design.py"
    out = tmp_path / "reference.json"
    completed = subprocess.run([sys.executable, str(script), "--out", str(out)],
                               capture_output=True, text=True, check=True)
    result = json.loads(completed.stdout)
    assert_reference_results(result)
    assert json.loads(out.read_text()) == result


def test_analytical_cli_executes_and_saves_results(tmp_path, capsys):
    assert main(["check", "--suite", "analytical", "--out", str(tmp_path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert_reference_results(result["appendix_a"])
    assert json.loads((tmp_path / "design.json").read_text()) == result


@pytest.mark.parametrize("extra", [["--suite", "native"], ["--suite", "all"],
                                 ["--suite", "analytical", "--phase", "confirmatory"]])
def test_unsupported_suites_and_phases_fail_without_results(tmp_path, extra):
    out = tmp_path / "unsupported"
    with pytest.raises(SystemExit) as error:
        main(["check", *extra, "--out", str(out)])
    assert error.value.code != 0
    assert not out.exists()


@pytest.mark.parametrize("entry", ["reference", "cli"])
def test_optimized_python_cannot_claim_unexecuted_assertion_checks(tmp_path, entry):
    out = tmp_path / "optimized"
    script = Path(__file__).resolve().parents[1] / "checks" / "validate_design.py"
    arguments = ([str(script), "--out", str(out / "reference.json")] if entry == "reference"
                 else ["-m", "ra.cli", "check", "--suite", "analytical", "--out", str(out)])
    completed = subprocess.run([sys.executable, "-O", *arguments], capture_output=True, text=True)
    assert completed.returncode != 0
    assert "assertions" in completed.stderr
    assert not out.exists()
