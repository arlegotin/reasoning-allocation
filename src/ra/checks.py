"""Analytical diagnostics only; no native performance or experiment claims."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import resource
import sys
import time
from types import MappingProxyType

from ra.ledger import CreditLedger


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


@dataclass(frozen=True)
class EvidenceRecord:
    """A synthetic evidence fixture; administrative copies retain its ID."""

    evidence_id: str
    posterior: float
    native_bound: float
    native_estimate: float

    def digest(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, allow_nan=False)
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class _Copy:
    lineage: str
    process: int
    mass: int
    evidence_id: str
    active: bool = True


def evidence_clone_diagnostic() -> dict[str, object]:
    evidence = MappingProxyType({"e1": EvidenceRecord("e1", 0.8, 2.0, 3.0)})
    before = evidence["e1"].digest()
    ledger = CreditLedger(10)
    ledger.reserve("parent", 4)
    parent = _Copy("parent", 0, 4, "e1")
    _require(ledger.close(parent.lineage) == 4, "split lost mass")
    copies = [replace(parent, lineage=name, mass=2) for name in ("left", "right")]
    for copy in copies:
        ledger.reserve(copy.lineage, copy.mass)
        ledger.spend(copy.lineage)
        _require(ledger.close(copy.lineage) == 1, "unused credit changed")
        _require(evidence[copy.evidence_id] is evidence[parent.evidence_id],
                 "copy introduced independent evidence")
    record = evidence[parent.evidence_id]
    _require(record.digest() == before, "credit changed evidence or native values")
    _require(record.posterior == 0.8 and record.native_bound == 2.0
             and record.native_estimate == 3.0, "evidence fixture changed")
    return {"evidence_id": record.evidence_id, "administrative_copies": len(copies),
            "posterior": record.posterior, "native_bound": record.native_bound,
            "native_estimate": record.native_estimate,
            "before_hash": before, "after_hash": record.digest(),
            "balances": ledger.snapshot(), "kind": "analytical_fixture"}


def coupled_administration(seed: int = 0) -> dict[str, object]:
    """Additional split/merge/cancel/spawn adversary; Appendix A is unchanged.

    Zero-mass canceled records remain in both representations. Each process has
    one immutable evidence record. The two samplers use equal independent RNG
    states; population weights are grouped in the queue's process order.
    """
    reference = _reference_module()
    ledger = CreditLedger(1000)
    evidence = MappingProxyType({f"e{i + 1}": EvidenceRecord(f"e{i + 1}", 0.8, 2.0, 3.0)
                                for i in range(2)})
    before = {key: record.digest() for key, record in evidence.items()}
    copies: list[_Copy] = []
    queue = {0: 100, 1: 100}
    for process in queue:
        lineage = f"initial:{process}"
        ledger.reserve(lineage, 100)
        copies.append(_Copy(lineage, process, 100, f"e{process + 1}"))
    rng_pop, rng_queue = random.Random(seed), random.Random(seed)
    work_pop, work_queue = {0: 0, 1: 0}, {0: 0, 1: 0}
    operations = {"split": 0, "merge": 0, "cancel": 0, "spawn": 0}
    decisions = 0

    def verify() -> None:
        _require(all(sum(copy.mass for copy in copies if copy.process == p) == mass
                     for p, mass in queue.items()), "process mass diverged")
        balance = ledger.snapshot()
        _require(sum(balance.values()) == 1000, "administrative credit not conserved")
        _require(balance["reserved"] == sum(queue.values()), "ledger and queue diverged")
        _require(all(copy.mass >= 0 and (copy.active or copy.mass == 0) for copy in copies),
                 "canceled lineage retained spendable mass")
        _require({key: record.digest() for key, record in evidence.items()} == before,
                 "administration updated evidence")
        _require(all(copy.evidence_id == f"e{copy.process + 1}" for copy in copies),
                 "evidence identity changed")
        _require(work_pop == work_queue, "work trajectory diverged")

    def close(index: int) -> int:
        copy = copies[index]
        returned = ledger.close(copy.lineage)
        _require(returned == copy.mass, "returned allowance diverged")
        copies[index] = replace(copy, mass=0, active=False)
        try:
            ledger.spend(copy.lineage)
        except ValueError:
            pass
        else:
            raise AssertionError("canceled lineage spent credit")
        return returned

    verify()
    for cycle in range(10):
        parent_index = next(i for i, copy in enumerate(copies) if copy.process == 0 and copy.active)
        parent = copies[parent_index]
        mass = close(parent_index)
        children = []
        for side, units in enumerate((mass // 2, mass - mass // 2)):
            lineage = f"{cycle}:split:{side}"
            ledger.reserve(lineage, units)
            children.append(len(copies))
            copies.append(replace(parent, lineage=lineage, mass=units))
        operations["split"] += 1
        verify()

        mass = sum(close(index) for index in children)
        lineage = f"{cycle}:merge"
        ledger.reserve(lineage, mass)
        copies.append(replace(parent, lineage=lineage, mass=mass))
        operations["merge"] += 1
        verify()

        index = next(i for i, copy in enumerate(copies) if copy.process == 1 and copy.active)
        canceled = copies[index]
        unused = close(index)
        queue[1] = 0  # Retain the canceled process's zero-mass queue record.
        operations["cancel"] += 1
        verify()

        lineage = f"{cycle}:spawn"
        ledger.reserve(lineage, unused)
        copies.append(replace(canceled, lineage=lineage, mass=unused))
        queue[1] += unused
        operations["spawn"] += 1
        verify()

        for _ in range(2):
            r_pop, r_queue = rng_pop.random(), rng_queue.random()
            _require(r_pop == r_queue, "random streams diverged")
            process_pop = reference.choose([(copy.process, copy.mass) for copy in
                                            sorted(copies, key=lambda copy: copy.process)], r_pop)
            process_queue = reference.choose(sorted(queue.items()), r_queue)
            _require(process_pop == process_queue, "selected process diverged")
            index = next(i for i, copy in enumerate(copies)
                         if copy.process == process_pop and copy.active and copy.mass)
            copy = copies[index]
            ledger.spend(copy.lineage)
            copies[index] = replace(copy, mass=copy.mass - 1)
            queue[process_queue] -= 1
            work_pop[process_pop] += 1
            work_queue[process_queue] += 1
            decisions += 1
            verify()
    return {"seed": seed, "matched_decisions": decisions, "operations": operations,
            "balances": ledger.snapshot(),
            "canceled_zero_mass_records": sum(not copy.active and copy.mass == 0 for copy in copies),
            "evidence_hashes_before": before,
            "evidence_hashes_after": {key: record.digest() for key, record in evidence.items()}}


def anti_lease() -> dict[str, object]:
    """A pays 1 in one step; B needs three steps beyond a two-step deadline."""
    deadline = 2

    def utility(path: str) -> float:
        return max(1.0 if path.count("A") >= 1 else 0.0,
                   1.0 if path.count("B") >= 3 else 0.0)

    long_path, one_step_path = "B" * deadline, "AB"
    long_value, one_step_value = utility(long_path), utility(one_step_path)
    _require(long_value < one_step_value, "anti-lease case lost sensitivity")
    return {"deadline_steps": deadline, "a_steps_to_payoff": 1, "b_steps_to_payoff": 3,
            "long_lease_path": long_path, "long_lease_utility": long_value,
            "one_step_path": one_step_path, "one_step_utility": one_step_value}


def _reference_path() -> Path:
    return Path(__file__).resolve().parents[2] / "checks" / "validate_design.py"


def _reference_module():
    # Load the one authoritative copy; no duplicated/reimplemented mathematics.
    # This project diagnostic requires the source checkout (also for direct use).
    path = _reference_path()
    spec = importlib.util.spec_from_file_location("ra_appendix_a", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load analytical reference: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_design_checks(out: Path) -> dict[str, object]:
    """Run only implemented analytical suites and persist a truthful scope."""
    start, cpu_start = time.perf_counter_ns(), time.process_time_ns()
    appendix = _reference_module().run_reference()
    _require(appendix["queue_population"]["matched_decisions"] == 102400,
             "Appendix A decision count changed")
    administration = [coupled_administration(seed) for seed in (0, 1, 42, 511)]
    clone = evidence_clone_diagnostic()
    anti = anti_lease()
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report = {
        "schema_version": 1, "success": True, "kind": "analytical",
        "claim_label": "locally measured check", "native_checks_executed": False,
        "suites_executed": ["appendix_a", "administrative_coupling", "evidence_clone", "anti_lease"],
        "reference_sha256": hashlib.sha256(_reference_path().read_bytes()).hexdigest(),
        "appendix_a": appendix, "administrative_coupling": administration,
        "evidence_clone": clone, "anti_lease": anti,
        "resources": {"elapsed_ns": time.perf_counter_ns() - start,
                      "process_cpu_ns": time.process_time_ns() - cpu_start,
                      "process_peak_rss_bytes": int(peak_rss * (1 if sys.platform == "darwin" else 1024)),
                      "scope": "in-process checks; excludes CLI imports and persistence; RSS is process lifetime peak"},
        "limitations": ["algebra and bookkeeping, not SCIP or MacBook performance measurements",
                        "native bound/estimate values are immutable synthetic fixtures",
                        "illustrative microsecond overhead values are supplied, not timed",
                        "source checkout required for the independently runnable Appendix A reference"],
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "design.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
