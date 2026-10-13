import json
import platform

from ra.doctor import discover_environment


def test_doctor_records_actual_architecture(tmp_path):
    report = discover_environment(tmp_path / "environment")
    assert report["architecture"] == platform.machine()
    assert report["interpreter"]["executable"]
    assert report["memory"]["installed_bytes"] > 0
    assert report["memory"]["available_bytes"] >= 0
    assert report["disk"]["free_bytes"] > 0
    assert report["native"]["scip_version"]
    assert report["native"]["lp_solver"]
    assert report["numerical_libraries"]["numpy_config"]
    assert report["numerical_libraries"]["scipy_config"]
    assert report["numerical_libraries"]["sklearn_version"]
    assert report["packages"]["pyscipopt"] == "6.3.0"
    assert report["native"]["parameters"]["parallel/maxnthreads"] == 1
    assert report["native"]["parameters"]["lp/threads"] == 1
    saved = json.loads((tmp_path / "environment" / "doctor.json").read_text())
    assert saved == report


def test_doctor_dry_run_writes_nothing(tmp_path):
    out = tmp_path / "absent"
    report = discover_environment(out, dry_run=True)
    assert report["dry_run"] is True
    assert not out.exists()


def test_doctor_preserves_native_failure_report(tmp_path, monkeypatch):
    from ra import doctor
    from ra.cli import main

    def unavailable():
        raise ImportError("deliberately unavailable SCIP")

    monkeypatch.setattr(doctor, "native_smoke", unavailable)
    out = tmp_path / "failed"
    assert main(["doctor", "--out", str(out)]) != 0
    saved = json.loads((out / "doctor.json").read_text())
    assert saved["success"] is False
    assert any("deliberately unavailable SCIP" in error for error in saved["errors"])


def test_doctor_cli_dry_run(tmp_path):
    from ra.cli import main

    out = tmp_path / "cli-absent"
    assert main(["doctor", "--out", str(out), "--dry-run"]) == 0
    assert not out.exists()


def test_doctor_does_not_require_optional_test_dependency(tmp_path, monkeypatch):
    from importlib import metadata
    from ra import doctor

    installed_version = metadata.version

    def without_pytest(name):
        if name == "pytest":
            raise metadata.PackageNotFoundError(name)
        return installed_version(name)

    monkeypatch.setattr(doctor.metadata, "version", without_pytest)
    report = discover_environment(tmp_path / "without-pytest")
    assert "packages" in report
    assert report["packages"]["pytest"] is None
    assert not any("numerical library discovery" in error for error in report["errors"])
