"""Read-only hardware diagnostics and a native, independently checked cover solve.

Diagnostic wall time is environment/setup cost, never a benchmark solver result.
Raw hardware command output may include machine identifiers; keep reports private.
"""

from __future__ import annotations

import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import resource
import shutil
import subprocess
import sys
import time

THREAD_SETTINGS = {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "VECLIB_MAXIMUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "BLIS_NUM_THREADS": "1",
}
COMMANDS = (
    ("uname", "-m"), ("sw_vers",), ("sysctl", "-n", "hw.memsize"),
    ("sysctl", "-n", "hw.logicalcpu"), ("df", "-k", "."),
    ("system_profiler", "SPHardwareDataType", "SPDisplaysDataType"),
    ("pmset", "-g"), ("pmset", "-g", "batt"),
    ("sysctl", "-in", "sysctl.proc_translated"), ("memory_pressure",),
    ("uptime",),
)


def _command(argv: tuple[str, ...] | list[str]) -> dict[str, object]:
    started = time.perf_counter_ns()
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=30)
        record = {"argv": list(argv), "status": "ok" if result.returncode == 0 else "failed",
                  "returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
    except (OSError, subprocess.TimeoutExpired) as exc:
        record = {"argv": list(argv), "status": "unavailable", "error": str(exc)}
    record["elapsed_ns"] = time.perf_counter_ns() - started
    return record


def _peak_rss_bytes() -> int:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(rss if sys.platform == "darwin" else rss * 1024)


def native_smoke() -> dict[str, object]:
    """Solve costs (1,2,1), rows (x0+x1>=1, x1+x2>=1); verify originals."""
    prior_threads = {key: os.environ.get(key) for key in THREAD_SETTINGS}
    try:
        os.environ.update(THREAD_SETTINGS)
        started = time.perf_counter_ns()
        import pyscipopt
        from pyscipopt import Model
        from threadpoolctl import threadpool_info, threadpool_limits

        imported = time.perf_counter_ns()
        with threadpool_limits(limits=1):
            model = Model("native-cover-smoke")
            model.hideOutput()
            model.setIntParam("parallel/maxnthreads", 1)
            model.setIntParam("lp/threads", 1)
            default_parameters = model.getParams()
            x = [model.addVar(name=f"x{i}", vtype="B", obj=cost)
                 for i, cost in enumerate((1, 2, 1))]
            model.addCons(x[0] + x[1] >= 1)
            model.addCons(x[1] + x[2] >= 1)
            solve_started = time.perf_counter_ns()
            model.optimize()
            solve_finished = time.perf_counter_ns()
            status = str(model.getStatus())
            if model.getNSols() == 0:
                raise RuntimeError(f"SCIP smoke returned no assignment ({status})")
            raw = [float(model.getVal(v)) for v in x]
            tolerance = float(model.getParam("numerics/feastol"))
            assignment = [int(round(v)) for v in raw]
            integral = all(abs(v - rounded) <= tolerance and rounded in (0, 1)
                           for v, rounded in zip(raw, assignment))
            feasible = integral and assignment[0] + assignment[1] >= 1 and assignment[1] + assignment[2] >= 1
            objective = sum(cost * v for cost, v in zip((1, 2, 1), assignment))
            solver_objective = float(model.getObjVal())
            if not feasible or objective != 2 or abs(solver_objective - objective) > tolerance or status != "optimal":
                raise RuntimeError("SCIP smoke failed original-space optimum/feasibility verification")
            native_file = str(Path(pyscipopt.scip.__file__).resolve())
            native_arch = _command(["file", native_file])
            banner = _command([sys.executable, "-c", "from pyscipopt import Model; m=Model(); m.printVersion(); m.printExternalCodeVersions()"])
            version_output = str(banner.get("stdout", ""))
            lp = re.search(r"\[LP solver: ([^]]+)\]", version_output)
            result = {
                "pyscipopt_version": pyscipopt.__version__,
                "scip_version": f"{model.getMajorVersion()}.{model.getMinorVersion()}.{model.getTechVersion()}",
                "lp_solver": lp.group(1) if lp else None,
                "version_banner": banner,
                "native_extension": native_file,
                "native_extension_sha256": hashlib.sha256(Path(native_file).read_bytes()).hexdigest(),
                "native_architecture": native_arch,
                "native_arm64": native_arch.get("status") == "ok" and "arm64" in str(native_arch.get("stdout", "")),
                "parameters": default_parameters,
                "status": status, "assignment": assignment, "raw_assignment": raw,
                "objective": objective, "solver_objective": solver_objective,
                "original_feasible": bool(feasible), "integrality_tolerance": tolerance,
                "import_ns": imported - started, "solve_ns": solve_finished - solve_started,
                "diagnostic_total_ns": time.perf_counter_ns() - started,
                "peak_rss_bytes": _peak_rss_bytes(),
                "thread_environment_before": prior_threads,
                "thread_environment": dict(THREAD_SETTINGS), "threadpools": threadpool_info(),
            }
            model.freeProb()
        return result
    finally:
        for key, value in prior_threads.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value



def discover_environment(out: Path, *, dry_run: bool = False) -> dict[str, object]:
    """Record actual diagnostics; a dry run runs no commands and writes nothing."""
    out = Path(out)
    if dry_run:
        return {"schema_version": 1, "dry_run": True, "out": str(out),
                "planned_commands": [list(argv) for argv in COMMANDS]}
    started = time.perf_counter_ns()
    report: dict[str, object] = {
        "schema_version": 1, "dry_run": False, "success": False,
        "architecture": platform.machine(), "os": platform.platform(),
        "interpreter": {"version": sys.version, "executable": sys.executable,
                        "architecture": platform.machine()},
        "errors": [],
    }
    errors = report["errors"]
    commands = [_command(argv) for argv in COMMANDS]
    report["commands"] = commands
    lookup = {tuple(record["argv"]): record for record in commands}
    hardware = str(lookup[COMMANDS[5]].get("stdout", ""))
    chip = re.search(r"Chip:\s*(.+)", hardware)
    report["chip"] = chip.group(1).strip() if chip else None
    translated = lookup[("sysctl", "-in", "sysctl.proc_translated")]
    report["rosetta"] = {"status": translated["status"],
                         "translated": str(translated.get("stdout", "")).strip() == "1" if translated["status"] == "ok" else None}
    report["power"] = {"settings": lookup[("pmset", "-g")],
                       "source": lookup[("pmset", "-g", "batt")]}
    try:
        import psutil
        memory = psutil.virtual_memory()
        report["memory"] = {"installed_bytes": memory.total, "available_bytes": memory.available,
                            "source": "psutil.virtual_memory", "used_percent": memory.percent,
                            "pressure": lookup[("memory_pressure",)]}
        report["cpu"] = {"logical_count": psutil.cpu_count(), "load_average": list(os.getloadavg())}
        disk = shutil.disk_usage(Path.cwd())
        report["disk"] = {"total_bytes": disk.total, "free_bytes": disk.free,
                          "used_bytes": disk.used, "path": str(Path.cwd())}
    except Exception as exc:
        errors.append(f"resource discovery: {type(exc).__name__}: {exc}")
    try:
        report["native"] = native_smoke()
        if not report["native"]["native_arm64"] or platform.machine() != "arm64":
            errors.append("Target-machine gate requires native ARM64 Python and SCIP")
        if not report["native"]["lp_solver"]:
            errors.append("Linked LP solver version could not be discovered")
    except Exception as exc:
        report["native"] = {"error": f"{type(exc).__name__}: {exc}"}
        errors.append(f"native smoke: {type(exc).__name__}: {exc}")
    try:
        import numpy
        import scipy
        import scipy.linalg
        import sklearn
        from threadpoolctl import threadpool_info, threadpool_limits
        configs = {}
        for name, library in (("numpy", numpy), ("scipy", scipy)):
            configs[f"{name}_config"] = library.show_config(mode="dicts")
        configs["sklearn_version"] = sklearn.__version__
        with threadpool_limits(limits=1):
            configs["threadpools"] = threadpool_info()
        report["numerical_libraries"] = configs
        report["packages"] = {}
        for name in ("pyscipopt", "numpy", "scipy", "scikit-learn", "psutil", "pytest", "threadpoolctl"):
            try:
                report["packages"][name] = metadata.version(name)
            except metadata.PackageNotFoundError:
                report["packages"][name] = None
    except Exception as exc:
        errors.append(f"numerical library discovery: {type(exc).__name__}: {exc}")
    report["target_m3_max_confirmed"] = platform.system() == "Darwin" and report["chip"] == "Apple M3 Max" and not errors
    # Unavailable commands remain visible rather than being replaced with assumptions.
    report["success"] = not errors
    report["discovery_ns"] = time.perf_counter_ns() - started
    report["peak_rss_bytes"] = _peak_rss_bytes()
    out.mkdir(parents=True, exist_ok=True)
    temporary = out / "doctor.json.tmp"
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    temporary.replace(out / "doctor.json")
    if "parameters" in report["native"]:
        (out / "scip-parameters.json").write_text(json.dumps(report["native"]["parameters"], indent=2, sort_keys=True) + "\n")
    return report
