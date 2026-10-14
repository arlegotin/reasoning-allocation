# Reasoning Allocation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and evaluate an overhead-aware local SCIP subtree allocator with enough correctness, cost accounting, and strong controls to support a bounded positive, negative, or blocked result.

**Architecture:** Preserve native SCIP search semantics and expose live nodes as primitive records to a stateful queue policy. A common observer and serial parent/worker harness define available deadline output; immutable manifests connect randomized training, tuning, protocol freeze, and clustered analysis. Population representations and transfer are gated follow-ups.

**Tech Stack:** Native ARM64 Python (start compatibility discovery at 3.12), PySCIPOpt (candidate 6.3.0), NumPy, SciPy, scikit-learn, psutil, pytest; exact versions and native binaries locked in WP00. PyTorch belongs only to permitted optional literature reproductions.

**Spec:** [2026-10-13-reasoning-allocation-design.md](../specs/2026-10-13-reasoning-allocation-design.md). Read it before implementing any task. This plan is unexecuted; all commands, test snippets, and commit messages below are instructions for future implementation.

## Global Constraints

- Work on the current branch; make meaningful commits at independently reviewable milestones.
- The core must run on one MacBook Pro with an M3 Max; actual hardware and environment are discovered, not assumed.
- The core requires no remote GPU, paid inference service, second machine, LLM, or PyTorch dependency.
- Primary timed comparisons use one solver worker and one native solver thread at a time.
- The primary endpoint charges a cold end-to-end request, including imports, model loading, setup, verification, observation, and finalization.
- Native default SCIP and seriously tuned native scheduling remain mandatory comparators.
- Training, tuning, unsuccessful attempts, censored work, and deadline overshoot remain visible and costed.
- Allocation scores, credit, multiplicity, native bounds, and evidence are separate state.
- No protected outcome is used for tuning; scientific changes after freeze require an amendment and appropriate fresh confirmation.

## Review Focus

- Delayed delivery and startup expiry: only parent-received, already validated output counts; before anchor publication utility is 0. Task 6 pins this behavior.
- Native restarts, deletion, and repeated callbacks: stale wrappers are never reused and each main-tree completion is charged once. Tasks 2 and 4 pin this behavior.
- Solver infinity sentinels, objective offsets, and large integer sums: feature normalization cannot corrupt valid bounds or integer feasibility. Tasks 5 and 10 pin this behavior.
- Censored/crashed requests and changed hashes on resume: preserve partial costs/output, reject incompatible reuse, and never treat a kill as an exact duration. Tasks 7 and 11 pin this behavior.
- Derivative-instance leakage and unsupported actions: splits follow templates, preprocessing follows training, and no unselected payoff is invented. Tasks 5, 11, 12, and 15 pin this behavior.

---

## Execution map and file ownership

The checkout contains documentation only. Create product files in the tasks that need them, not in a separate scaffolding pass. Use frozen dataclasses, explicit protocols, strict JSON parsing, pathlib, and standard-library hashing. SciPy CSR holds original binary incidence; original costs and checked objectives use integers. Full configuration resolution is recorded per request.

| Tasks | Work package | Files and responsibility |
| --- | --- | --- |
| 1–2 | WP00 | `pyproject.toml`, `requirements.lock`, `src/ra/{cli,doctor,types,scip_backend}.py`; runnable package and exercised native capability |
| 3–4 | WP01 | `checks/validate_design.py`, `src/ra/{checks,ledger,leases,candidates}.py`; exact bookkeeping and lease state machine |
| 5–8 | WP02 | `src/ra/{data,exact,config,provenance,observer,worker,runner,metrics,allocators}.py`; original instances, honest request harness, baseline policies |
| 9 | WP03 | `src/ra/pilot.py`, native/discovery configurations and headroom summaries; evidence-based continue/stop |
| 10–12 | WP04 | `src/ra/{features,collect,models,train}.py`, feature and model cards; randomized observed-action learner |
| 13–14 | WP05 | pooled and attribution policies, baseline register/cards/patches; strong contenders and bounded claims |
| 15 | WP06 | `src/ra/{freeze,stats}.py`, frozen protocol/config/manifest; pilot-calibrated protected evaluation |
| 16–17 | WP07 | runner/metrics/stats/report extensions; fixed requests and paired uncertainty |
| 18 | WP08 | `src/ra/population.py`, robustness configurations; discriminating attribution and coupled implementation |
| 19 | WP09 | `src/ra/transfer.py`, separate transfer protocols; gated independent-set/MIPLIB tests |
| 20 | WP10 | `src/ra/report.py`, final report/reproduction/claims manifests; valid handoff even after early stop |

`src/ra/types.py` is the shared record boundary, extended by its owning tasks. Configuration defaults live in versioned JSON and resolve to immutable values; reject unknown fields. `PROGRESS.md`, `DECISIONS.md`, and `artifacts/status.json` are updated in every milestone with checks, resources, artifact hashes, and the next gate. Large wheels, traces, models, generated instances, `.venv`, and runtime output are ignored by Git; compact reproducible summaries and manifests can be deliberately versioned. Test examples below use `pytest` and the owning task's declared imports. Named case fixtures belong in that task's test module: they construct exactly the scenario described by the adjacent test step, using earlier task interfaces, without solver timing guesses or protected data.

Run tasks sequentially by dependency. Task 14 can investigate optional baseline access after Task 9, but must finish before Task 15. A gate can stop implementation and jump to Task 20 with a scoped negative/blocked report. No later task overrides a failed gate. Tasks 18–19 require their stated evidence; they are not mandatory escalation after any p-value. The initial planning delivery does not authorize running these experiments now.

## Task 1: Runnable package, environment discovery, and native smoke (WP00)

**Files:** Create `pyproject.toml`, `.gitignore`, `src/ra/__init__.py`, `src/ra/cli.py`, `src/ra/doctor.py`, `tests/test_doctor.py`, `tests/test_scip_smoke.py`; modify `README.md`, `PROGRESS.md`, `DECISIONS.md` during execution; generate `requirements.lock`, `artifacts/environment/*`, `artifacts/licenses.json`.

**Interfaces:** Consumes system commands and candidate dependency stack from spec §10. Produces `doctor.discover_environment(out: Path, *, dry_run: bool = False) -> dict[str, object]`, `doctor.native_smoke() -> dict[str, object]`, and `cli.main(argv: list[str] | None = None) -> int`. `pyproject.toml` defines package `ra` from `src` and entry point `ra = ra.cli:main`. A doctor failure exits nonzero and preserves its report.

- [x] **Step 1: Discover the real machine and resolve the candidate environment.** Save outputs of `uname -m`, `sw_vers`, `sysctl -n hw.memsize`, `sysctl -n hw.logicalcpu`, `df -k .`, `system_profiler SPHardwareDataType SPDisplaysDataType`, `pmset -g`, Python version/architecture/executable. Run each independently and retain unavailable-command status. Record installed and available memory, disk, power mode, and Rosetta status.
- [x] **Step 2: Create a compatible environment without replacing system Python.** Candidate commands are `python3.12 -m venv .venv`, `.venv/bin/python -m pip install --upgrade pip`, then `.venv/bin/python -m pip install --only-binary=:all: --report artifacts/environment/install.json 'pyscipopt==6.3.0' numpy scipy scikit-learn psutil pytest`. Try another supported ARM64 interpreter intersection if resolution fails. Download resolved wheels to `artifacts/environment/wheels/`; write an exact version/artifact-SHA256 lock and retain metadata/licenses/native versions. A source build requires a recorded toolchain and native parity checks.
- [x] **Step 3: Write the failing smoke and doctor tests.** `test_native_cover_optimum` directly builds binary variables with costs `(1,2,1)` and rows `(x0+x1 >= 1, x1+x2 >= 1)`, asserting objective 2 and original feasibility. `test_doctor_records_actual_architecture` asserts recorded architecture equals `platform.machine()` and includes interpreter, memory, disk, and linked SCIP fields. `test_doctor_dry_run_writes_nothing` asserts the requested output directory remains absent.

```python
def test_native_cover_optimum():
    result = native_smoke()
    assert result["objective"] == 2
    assert result["original_feasible"] is True
```
- [x] **Step 4: Run the red tests.** `.venv/bin/python -m pytest tests/test_doctor.py tests/test_scip_smoke.py -q` must fail because `ra.doctor` is absent, not because of an unrelated solver failure.
- [x] **Step 5: Implement the package and doctor signatures.** Keep discovery read-only except requested report output. Add `doctor --out PATH [--dry-run]` and help/error paths. Print installed PySCIPOpt and linked native versions, full parameter dump, BLAS/OpenMP/thread settings, and import/solve time/RSS. Native architecture must be ARM64 to pass the target-machine gate; another platform may run diagnostics but cannot claim M3 feasibility.
- [x] **Step 6: Verify.** Install the editable package using `.venv/bin/python -m pip install --no-deps -e .`; run `.venv/bin/python -m pip check`, the two test modules, `python -m ra.cli --help`, and `python -m ra.cli doctor --out artifacts/environment`. Expected: no dependency conflicts, passing tests, exit 0 with truthful architecture/native-version report on the target. Installation and discovery costs are recorded, not treated as solver timings.
- [x] **Step 7: Commit.** Stage package metadata, doctor/CLI, tests, documentation, and exact lock; commit `feat: add environment discovery and native SCIP smoke`. Do not stage downloaded wheels or fabricated environment outputs.

## Task 2: Live node adapter and capability gate (WP00)

**Files:** Create `src/ra/types.py`, `src/ra/scip_backend.py`, `tests/test_scip_lifecycle.py`, `tests/fixtures/capability_cases.json`; extend `doctor.py`; generate `artifacts/capabilities.json`. A native bridge, if necessary, belongs in `src/ra/native/run_identity.*` with installed-build source/ABI records.

**Interfaces:** Produces `NodeKey`, `NodeRecord`, `DecisionContext`, `Allocation` exactly as spec §4; `ScipBackend.live_frontier() -> list[NodeRecord]`, `validated_progress() -> tuple[float, float, float]` ordered `(primal_original, dual_original, utility_local)`, `request_stop() -> None`, `resolve_live(key: NodeKey) -> object`, and `capture_capabilities(out: Path) -> dict[str, object]`. `StaleNodeError` subclasses `ValueError` and is exported from `scip_backend.py`. Native objects never escape the callback-facing adapter. Completion records identify epoch, native number, main-tree origin, and deduplicated event kind.

- [x] **Step 1: Write failing lifecycle tests.** `test_live_resolution_rejects_deleted_key` asserts deleted keys raise `StaleNodeError`; `test_restart_advances_epoch_and_rejects_old_key` asserts a restart changes epoch even when a number is reused; `test_repeated_completion_is_counted_once` sends the same completed-node event twice and asserts count 1; `test_deleted_unprocessed_node_costs_no_credit` asserts count 0; `test_comparator_is_immutable_total_order` checks depth descending/number ascending, including antisymmetry/transitivity. Test native plugin selection returns `{'selnode': live_node}`.

```python
def test_live_resolution_rejects_deleted_key(deleted_backend_and_key):
    backend, key = deleted_backend_and_key
    with pytest.raises(StaleNodeError):
        backend.resolve_live(key)
```
- [x] **Step 2: Run red.** `python -m pytest tests/test_scip_lifecycle.py -q`; expected missing adapter/types, with all later native smoke failures investigated rather than skipped.
- [x] **Step 3: Implement primitives and the adapter.** Deduplicate current open lists, store primitive parent links/reference counts, and use installed solver infinity conventions. Handle completion/root/subsolver distinctions, event registration cleanup, bound/incumbent/deletion events, interruption, and original/transformed objective channels. Comparator uses only immutable depth/number. Missing ancestry is an adapter error.
- [x] **Step 4: Exercise actual native behavior.** Save a normal-enhancement fixture plus explicitly labeled diagnostics that produce branching/deletion and an actual native restart. Discover valid restart settings from installed parameters; extend bounded fixture search until a recorded run-identity transition occurs. Mock restart tests alone cannot pass. Verify Python lifecycle hooks or implement the version-checked bridge; if reliable detection cannot be exercised, mark the primary adapter gate blocked. Do not silently disable restarts.
- [x] **Step 5: Verify.** `python -m pytest tests/test_scip_smoke.py tests/test_scip_lifecycle.py -q` and `python -m ra.cli doctor --out artifacts/environment`; expected passing exercised required capabilities, completion/native-counter reconciliation with documented differences, and original-space objective 2. `capabilities.json` distinguishes exercised, missing, and blocked operations.
- [x] **Step 6: Commit.** `git add src/ra/types.py src/ra/scip_backend.py src/ra/doctor.py tests/test_scip_lifecycle.py tests/fixtures/capability_cases.json`; include any justified bridge/source metadata, then `git commit -m "feat: validate SCIP node lifetime and event capabilities"`. WP00 may pass only with real lifecycle evidence.

## Task 3: Exact administrative and analytical diagnostics (WP01)

**Files:** Create `checks/validate_design.py`, `src/ra/checks.py`, `src/ra/ledger.py`, `tests/test_ledger.py`, `tests/test_equivalence.py`, `tests/test_design_checks.py`; extend `cli.py`.

**Interfaces:** Produces `CreditLedger(total_units: int)` with `reserve(lease_id: str, units: int) -> None`, `spend(lease_id: str, units: int = 1) -> None`, `close(lease_id: str) -> int`, `snapshot() -> dict[str, int]` (keys `available`, `reserved`, `spent`); all balances are nonnegative integers. `checks.run_design_checks(out: Path) -> dict[str, object]` runs the supplied Appendix A plus anti-lease diagnostic. Evidence is referenced by immutable IDs and never updated by credit methods.

- [x] **Step 1: Write failing invariant tests.** Assert initial budget equals available + reserved + spent; closing a lease twice raises without adding credit; canceled lineages cannot spend; split/merge/spawn/cancel cycles preserve mass; cloning evidence ID `e1` leaves its posterior at 0.8 and native bound/estimate unchanged. `test_appendix_a_expected_results` pins 512 seeds, 102400 decisions, 0.6/1.0/`BB`, and overhead ratios approximately 1.12/0.84. `test_long_lease_can_lose` gives A utility 1 after one step and B no payoff within the two-step deadline, asserting a B lease loses to A.

```python
def test_unused_allowance_returns_once():
    ledger = CreditLedger(total_units=10)
    ledger.reserve("lease", 4)
    ledger.spend("lease", 2)
    assert ledger.close("lease") == 2
    assert ledger.snapshot() == {"available": 8, "reserved": 0, "spent": 2}
    with pytest.raises(ValueError):
        ledger.close("lease")
    assert ledger.snapshot()["available"] == 8
```
- [x] **Step 2: Run red.** `python -m pytest tests/test_ledger.py tests/test_equivalence.py tests/test_design_checks.py -q`; expected absent ledger/check runner.
- [x] **Step 3: Implement exact conservation and diagnostics.** Copy the spec's complete standard-library Appendix A into `checks/validate_design.py`, preserve environment fields from the executing machine, and adapt its entry point without altering expected mathematics. Couple queue/population process-level masses and RNG; include canceled-zero-mass records and immutable evidence hashes. Implement no native performance claim.
- [x] **Step 4: Verify.** Run `python checks/validate_design.py`, the three test modules, and `python -m ra.cli check --suite analytical --out artifacts/checks`. Expected exact matched decisions and budget/evidence checks, sensitive delayed and anti-lease examples. Outputs record platform and whether they are analytical/native.
- [x] **Step 5: Commit.** Stage the checks, ledger, tests, and CLI; commit `feat: add exact allocation and evidence invariants`.

## Task 4: Lease state machine and deterministic candidate support (WP01)

**Files:** Create `src/ra/leases.py`, `src/ra/candidates.py`, `tests/test_lease.py`, `tests/test_candidates.py`; extend `types.py`, `scip_backend.py`.

**Interfaces:** Produces `LeaseController.begin(allocation: Allocation, decision_start_ns: int) -> None`, `on_completed(key: NodeKey) -> None`, `next_node(frontier: Sequence[NodeRecord], now_ns: int) -> NodeKey | None`, `cancel(reason: str) -> None`, and `finish(end_ns: int, reason: str) -> LeaseOutcome`. `CandidatePool` stores ordered primitive records, complete IDs/hash/strata, RNG state; `build_pool(frontier: Sequence[NodeRecord], k: int | None, rng: random.Random) -> CandidatePool`. `LeaseOutcome` includes root/length/work, entry/dispatch/end, end reason, natural completion and censoring flags; later Task 11 adds reconstructed targets.

- [x] **Step 1: Write failing lease tests.** Root is selected first; descendant order follows greatest depth then estimate/bound/number; a length-2 lease ends after two distinct completion events, not two selections; a new incumbent does not end it; exhaustion returns unused credits once; unrelated nodes never continue it; empty frontier returns `None`; restart/ancestor deletion cancels it; deadline with live nodes requests stop and returns a legal live node through the adapter. Repeated native calls must not duplicate spending.
- [x] **Step 2: Write failing pool tests.** `K<5` and frontier size at most `K` use all nodes; a larger pool has exactly `K` unique live keys, deterministic ranking ties, reproducible random fill under overlapping strata, and no removal from the live frontier. Check `K=32` and recorded hash/RNG parity.

```python
def test_pool_overlap_fills_unique_slots(overlapping_frontier_100):
    before = tuple(node.key for node in overlapping_frontier_100)
    pool = build_pool(overlapping_frontier_100, 32, random.Random(7))
    assert len({node.key for node in pool.records}) == 32
    assert tuple(node.key for node in overlapping_frontier_100) == before
```
- [x] **Step 3: Run red.** `python -m pytest tests/test_lease.py tests/test_candidates.py -q`; expected absent lease/pool APIs.
- [x] **Step 4: Implement the state machine and pool.** Use Task 2 primitive ancestry and Task 3 credit methods. Continuation scans are timed inside lease body. Cancellation/deadline/empty-tree residual administration is retained. Reject nonpositive lengths/invalid pool configurations. A lease controller's `None` means no continuation and asks the selector to rebid or stop; the actual native callback returns `None` only for an empty global frontier. Keep native wrapper resolution inside the adapter at selection return.
- [x] **Step 5: Verify.** Run Tasks 2–4 test modules and native logical-budget fixtures; expected identical repeated-seed selected-node traces, exact credit identities, no stale keys, and legal callback timeout behavior.
- [x] **Step 6: Commit.** Stage affected modules/tests; commit `feat: implement bounded subtree leases and candidate pools`.

## Task 5: Deterministic covers, integer checks, and split provenance (WP01/WP02)

**Files:** Create `src/ra/data.py`, `src/ra/exact.py`, `src/ra/config.py`, `src/ra/provenance.py`, `tests/test_enumeration.py`, `tests/test_generators.py`, `tests/test_splits.py`, `tests/test_objectives.py`; extend `types.py`, `cli.py`; create a discovery-only `configs/workload_probes.json`.

**Interfaces:** Produces `CoverInstance(instance_id, template_id, cell_id, incidence, costs, lineage)`; `GeneratorCell` implements spec §7 recipe parameters. `generate_cover(cell: GeneratorCell, template_seed: int) -> CoverInstance`; `verify_cover(instance: CoverInstance, values: Sequence[float], integrality_tolerance: float) -> VerifiedAssignment`; `enumerate_cover(instance: CoverInstance) -> VerifiedAssignment`; `derive_seed(master: str, split: str, template_index: int) -> int`; `instance_hash(instance: CoverInstance) -> str`; `load_config(path: Path, kind: str) -> dict[str, object]`. `VerifiedAssignment` contains binary vector, integer objective, and content hash; invalid input raises a typed error.

- [x] **Step 1: Write failing exact/generator tests.** Assert the two-row costs `(1,2,1)` optimum is 2; all-one objective is 4; nonempty rows/unique incidence/positive integer costs for every family; impossible sample counts reject; clones use floor-count and bridge-before-clone order; costs remain positive. Check objective/coverage sums above uint8 and int64 range with Python-integer fallback, near-tolerance rounding, and rejection of unrounded fractions.
- [x] **Step 2: Write failing provenance tests.** Repeat cell/seed gives identical canonical arrays/hash; different split labels derive different seeds; permutations/scalings stay with their original template; a reused template across train/confirmatory rejects even if matrix hashes differ. Unknown config fields and negative weights reject.

```python
def test_original_integer_objective(tiny_two_row_cover):
    result = verify_cover(tiny_two_row_cover, (1.0, 0.0, 1.0), 1e-6)
    assert result.objective == 2
    assert enumerate_cover(tiny_two_row_cover).objective == 2
    with pytest.raises(ValueError):
        verify_cover(tiny_two_row_cover, (0.5, 0.0, 1.0), 1e-6)
```
- [x] **Step 3: Run red.** `python -m pytest tests/test_enumeration.py tests/test_generators.py tests/test_splits.py tests/test_objectives.py -q`; expected missing project APIs.
- [x] **Step 4: Implement generation and exact validation.** Match the three recipes and probe grid in the spec, preserving original CSR incidence and integer costs. Use enumeration only at a measured affordable tiny scale; do not hard-code an unmeasured large `n`. Canonicalize incidence/cost hashing and store generator version/lineage. Add `generate --config PATH --split LABEL [--out PATH] [--dry-run]`; default out is `data/LABEL`. Probe manifest is not the final workload manifest.
- [x] **Step 5: Verify.** Run the four tests and all selectors implemented so far on enumerated tiny covers with ample logical budget. Expected exact integer feasibility/optimum for every complete policy, correct positive affine utility transformation, and deterministic generation. Record enumeration cost and prevent cross-split derivatives.
- [x] **Step 6: Commit.** Stage data/exact/config/provenance/types/tests/CLI and probe configuration; commit `feat: add reproducible weighted cover workloads and exact checks`.

## Task 6: Validated observer and cold parent/worker deadline (WP02)

**Files:** Create `src/ra/observer.py`, `src/ra/worker.py`, `src/ra/runner.py`, `src/ra/metrics.py`, `tests/test_deadlines.py`, `tests/test_observer.py`, `tests/test_worker.py`; extend `types.py`, `scip_backend.py`.

**Interfaces:** Produces `ProgressRecord` fields from spec §11 (including `child_ns`, `receipt_ns`), `Observer.validate_incumbent(values: Sequence[float], event_ns: int) -> ProgressRecord`, `Observer.observe_dual(bound_original: float, event_ns: int) -> ProgressRecord`, `Observer.available_local() -> tuple[float, float, float]` ordered as Task 2; `metrics.utility(p: float, d: float, p0: int, d0: float = 0.0) -> float`; `metrics.progress_at(records: Sequence[ProgressRecord], deadline_ns: int, p0: int) -> AvailableProgress`; `worker.execute_request(request_path: Path) -> int`; `runner.run_request(request: Request, out: Path) -> Attempt`. `Request` holds fully resolved scientific/config hashes, input/model paths, method/seeds/budget/watchdog/thread settings; parent fills absolute deadline at launch, outside scientific configuration hashes. `AvailableProgress` has `assignment_available: bool` and `utility: float` alongside original primal/dual and assignment identity.

- [x] **Step 1: Write failing receipt-boundary tests.** A validated child event at ns 80 received at ns 101 does not count for deadline 100; receipt exactly at 100 does. No published anchor gives availability false and utility 0. With `P0=10`, published `(P=8,D=2)` gives 0.4. Inject improved post-deadline output and assert unchanged score; duplicate/out-of-order sequences reject. Timer alignment failure blocks label reconstruction instead of assuming clocks match.

```python
def test_late_receipt_cannot_publish_an_anchor(late_anchor_record):
    assert late_anchor_record.child_ns == 80
    assert late_anchor_record.receipt_ns == 101
    result = progress_at([late_anchor_record], deadline_ns=100, p0=10)
    assert result.assignment_available is False
    assert result.utility == 0.0
```
- [x] **Step 2: Write failing observer/subprocess tests.** Original feasibility invalidates a false incumbent; dual above checked primal beyond tolerance gives `numerical_alarm`; an original-space offset/scaling transform preserves utility; startup that outlasts the deadline produces `startup_timeout`, no available assignment, utility 0. A deliberately delayed transmission changes availability even if search is identical. A normal tiny cold request includes imports/loading/anchor and returns a verified objective.
- [x] **Step 3: Run red.** `python -m pytest tests/test_deadlines.py tests/test_observer.py tests/test_worker.py -q`; expected missing observer/worker/runner APIs. Use injected clocks for exact boundary assertions; subprocess integration tests assert ordering, not fragile microsecond thresholds.
- [x] **Step 4: Implement the common observer and process path.** Start parent timer immediately before launch; initialize known lower bound and verified anchor in the charged worker; send compact validated records over a local pipe; stamp parent receipt on read. Keep child-local runtime progress separate. Bind event/polling fallback uniformly and test missed/terminal progress. Request cooperative stop and retain legal native selection behavior. Configure all threads before numerical imports; load the model/instance inside the worker.
- [x] **Step 5: Verify.** Run the three modules plus native smoke; expected exact receipt semantics and integer verification. Record alignment, cold startup and return/release, valid fallback, post-deadline rejection, and startup timeout in `artifacts/harness_validation.json` with raw traces.
- [x] **Step 6: Commit.** Stage observer/worker/runner/metrics/types/backend/tests; commit `feat: measure validated solver output at end-to-end deadlines`.

## Task 7: Disjoint resources, atomic attempts, and recovery (WP02)

**Files:** Extend `src/ra/ledger.py`, `runner.py`, `worker.py`, `types.py`; create `tests/test_resource_ledger.py`, `tests/test_recovery.py`; create `artifacts/status.json` at execution time.

**Interfaces:** Produces `TimeLedger.enter(category: str, now_ns: int) -> None`, `leave(now_ns: int) -> None`, `summary(end_ns: int) -> dict[str, int]` with exclusive totals; `runner.publish_attempt(attempt: Attempt, directory: Path) -> Path`; `runner.resume_requests(requests: Sequence[Request], root: Path) -> list[Request]`; `Attempt` stores all spec §11 fields, immutable IDs, status, valid progress, censored-duration flag, resource-release and cumulative prior-attempt costs. Status enum is exactly the seven spec values.

- [x] **Step 1: Write failing ledger/recovery tests.** Exclusive worker categories plus residual equal worker elapsed; diagnostic nested inference does not double-count; parent overlap is not added twice to elapsed. Inject interruption after model load, after valid publication, in lease work, and during finalization; partial attempt stays visible and rerun has a new ID. A changed code/model/build/config hash rejects resume. OOM/method errors retain latest valid progress and all spent resources. Watchdog kill stores a duration lower bound and overshoot; correctness alarms quarantine the configuration.

```python
def test_resume_rejects_changed_model(changed_model_request_and_root):
    request, root = changed_model_request_and_root
    with pytest.raises(ValueError, match="hash"):
        resume_requests([request], root)
```
- [x] **Step 2: Run red.** `python -m pytest tests/test_resource_ledger.py tests/test_recovery.py -q`; expected absent timing/persistence interfaces.
- [x] **Step 3: Implement timing and atomic recovery.** Use monotonic integer ns and nonoverlapping worker categories; separately record parent resource observations. Sample RSS/CPU with measured observer cost. Write/flush temporary attempt files, atomically publish a complete manifest, preserve partials, and schedule missing requests only under identical hashes. Never pickle native search or splice prefixes. Operational status writes evidence paths/hashes and next action; protocol amendments remain separate.
- [x] **Step 4: Verify.** Run recovery/ledger/deadline tests and a paired interrupted-tiny-run drill. Expected reconstructible last valid utility, no hidden costs/dropped attempts, exact logical conservation, and consistent resource reconciliation up to recorded timer resolution.
- [x] **Step 5: Commit.** Stage modules/tests and compact status/schema evidence; commit `feat: preserve request costs and recover immutable attempts`.

## Task 8: Native and shared-adapter controls (WP02)

**Files:** Create `src/ra/allocators.py`, `tests/test_allocators.py`, `tests/test_harness_controls.py`, `configs/native/default.json`, `configs/native/search_space.json`, `configs/exploratory.json`; extend `config.py`, `runner.py`, `cli.py`.

**Interfaces:** Produces `Allocator.choose(context: DecisionContext, candidates: Sequence[NodeRecord], lease_lengths: Sequence[int]) -> Allocation`, `observe(outcome: LeaseOutcome) -> None`; `make_allocator(method_config: dict[str, object], seed: int) -> Allocator`; `resolve_native_overrides(params: dict[str, object], overrides: dict[str, object]) -> dict[str, object]`; `runner.run_schedule(config_path: Path, phase: str, out: Path, *, resume: bool = False, dry_run: bool = False) -> list[Attempt]`. Native B0 avoids custom selectors/scans; B1 uses installed native plugin priorities/parameters.

- [x] **Step 1: Write failing selection/config tests.** Pin deterministic estimate/bound/depth/FIFO/round-robin choices and seeded uniform selection. The budget-sensitive rule starts alternating minimum bound every other rebid and uses configured remaining-time bins/lengths. Unsupported native names/ranges reject. Recreating a worker never inherits prior overrides. B0 retains installed defaults except shared scientific/thread/resource settings.

```python
def test_native_override_must_exist_in_installed_build():
    with pytest.raises(ValueError):
        resolve_native_overrides({"limits/time": 10.0}, {"invented/param": 1})
```
- [x] **Step 2: Write failing harness controls.** Identical policy under two names has identical logical work/output with coupled seeds; deliberate delayed publication worsens its deadline score; tiny delayed-payoff optimum distinguishes the correct scheduler. Ensure method order is deterministic under run-order seed and serial throughout timed phases.
- [x] **Step 3: Run red.** `python -m pytest tests/test_allocators.py tests/test_harness_controls.py -q`; expected absent factory/schedule APIs.
- [x] **Step 4: Implement controls and command routing.** Add `run --config PATH --phase PHASE [--out PATH] [--resume] [--dry-run]`; default out is `artifacts/runs/PHASE`. Validate configured discovery/train/validation input namespaces; confirmatory mode stays unavailable until Task 15. Record B0/B1 settings and all B2 variants. Initialize estimate/plunge tuning from actual installed parameter dump and permitted native selectors.
- [x] **Step 5: Verify.** Run both test modules and serial discovery null/positive-control requests. Compare minimal common observer against diagnostic and uninstrumented native runs; report measured observation effect/uncertainty, simplify common observation if material, and repeat the pilot. Never subtract estimated instrumentation cost from reported outcomes.
- [x] **Step 6: Commit.** Stage controls/configs/tests/CLI; commit `feat: add strong native scheduling and harness controls`. WP02 passes only after reconstruction, timer, sensitivity, and observer checks.

## Task 9: Native-only workload pilot and headroom decision (WP03)

**Files:** Create `src/ra/pilot.py`, `tests/test_pilot_gates.py`; generate `configs/workload_manifest.json`, `artifacts/pilot/headroom.csv`, `artifacts/pilot/resource_forecast.json`; update native/exploratory configs and progress/decisions.

**Interfaces:** Produces `pilot.summarize_headroom(attempts: Sequence[Attempt]) -> dict[str, object]`, `pilot.recommend_population(discovery_summary: dict[str, object]) -> dict[str, object]`, and `pilot.forecast(stage: str, observed_costs: Sequence[dict[str, object]], design: dict[str, object]) -> dict[str, object]`. Recommendations become a recorded finite manifest, not automatic post-result filtering.

- [x] **Step 1: Write failing gate tests.** A root-only population records proxy insufficiency, not H1 falsification; a schedule envelope is labeled finite-tested and not universal; failed/OOM/easy instances remain in summaries; any learned/protected record rejects native-only population selection. Memory admission never allows timed worker concurrency above 1. Forecast uncertainty includes failed attempts/overshoot.

```python
def test_learned_outcome_cannot_select_population(learned_discovery_summary):
    with pytest.raises(ValueError, match="native"):
        recommend_population(learned_discovery_summary)
```
- [x] **Step 2: Run red.** `python -m pytest tests/test_pilot_gates.py -q`; expected missing pilot summaries.
- [x] **Step 3: Implement headroom and resource summaries.** Record root/nonsteerable time, frontier distribution, main-tree/LP throughput, switching costs, and diverse native/fixed-lease schedules. Compute the brief's overhead headroom arithmetic using measured inputs; label illustrative versus measured quantities. Store start-at-64 geometric probes, valid row ratios/degrees/blocks, and measured reasons for stopping escalation.
- [x] **Step 4: Execute discovery and tune native on validation.** `python -m ra.cli run --config configs/exploratory.json --phase pilot`. Escalate sizes only from native behavior and resources; inspect delayed payoff without candidate-model results. Expand native tuning around promising settings while its trend can change the conclusion. Profile all-frontier and `K=32,128,512`, supported geometric lengths, timer/invocation floor, minimal observer, and safe-return tails. These observations calibrate later grids, watchdog, and cold deadline scales.
- [x] **Step 5: Write the gate decision.** Continue for measurable steerable headroom/heterogeneous schedules or a specific unresolved delayed-payoff prediction; prospectively narrow/revise an insensitive proxy; or stop for measured low headroom and go to Task 20. Select finite cells/weights and split hashes before training; retain natural easy cases. No automatic numeric success threshold replaces judgment/evidence.
- [x] **Step 6: Verify and commit.** Run pilot tests; reconstruct headroom/resource summaries from manifests; inspect declared population against native-only provenance. Commit compact configs/evidence/decision with `research: lock native pilot population and allocation headroom`. WP03 must explicitly justify Task 10.

## Task 10: Whitelisted local features and normalization (WP04)

**Files:** Create `src/ra/features.py`, `configs/features.json`, `tests/test_features.py`; extend `types.py`, `config.py`.

**Interfaces:** Produces `FeatureSchema` with ordered names/units/origins/caps/masks/hash; `FeatureBatch` with float64 matrix, `(NodeKey,length)` action rows, and schema hash; `features.build_features(context: DecisionContext, candidates: Sequence[NodeRecord], lengths: Sequence[int], ancestry: Mapping[NodeKey, object], schema: FeatureSchema) -> FeatureBatch`. `features.normalize_transformed(value: float, lower: float, cutoff: float, is_infinity: Callable[[float], bool]) -> tuple[float, dict[str, bool]]` returns model data only.

- [x] **Step 1: Write failing feature tests.** Solver sentinel `1e20` reported infinite is masked even though IEEE-finite; neither finite reference gives scale 1; negative/zero references and offset/scaling preserve semantic differences. Feature clipping adds an out-of-range flag and never edits native records. Post-action/teacher/optimum fields reject; schema ordering/hash are stable; missing ancestry masks only optional stored summaries, while required path absence remains an adapter error. Actual matrix dtype is float64 and dimensions are recorded.

```python
def test_solver_infinity_is_not_ieee_finiteness():
    value, masks = normalize_transformed(1e20, 0.0, 1e20,
                                        lambda x: abs(x) >= 1e20)
    assert masks["value_infinite"] is True
    assert math.isfinite(value)  # finite model placeholder; native data unchanged
```
- [x] **Step 2: Run red.** `python -m pytest tests/test_features.py -q`; expected missing feature interfaces.
- [x] **Step 3: Implement only spec §6 fields.** Bound lineage history; use child-local pre-allocation utility under its explicit field name. Action rows cover exactly pool × supported lengths. Implement SCIP-infinity-aware masks and training-range caps; leave learned imputation/scales for Task 12. Time extraction separately and keep feature buffers bounded.
- [x] **Step 4: Verify.** Run feature/objective/native-lifecycle tests; inspect a discovery feature shard against the whitelist and native objective-space conversions. Expected no privileged inputs, correct infinity behavior, and recorded matrix dimension/bytes/extraction cost.
- [x] **Step 5: Commit.** Stage features/schema/tests/types/config; commit `feat: add bounded local allocation features`.

## Task 11: Randomized leases and authoritative observed targets (WP04)

**Files:** Create `src/ra/collect.py`, `tests/test_collection.py`, `tests/test_lease_labels.py`; extend `types.py`, `leases.py`, `worker.py`, `runner.py`, `cli.py`, exploratory config; write `data/traces/train/*` during execution.

**Interfaces:** Produces `collect.mixture_probability(selected: tuple[NodeKey, int], heuristic: tuple[NodeKey, int], pool_size: int, length_count: int, epsilon: float) -> float`; `collect.label_leases(leases: Sequence[LeaseOutcome], progress: Sequence[ProgressRecord], deadline_ns: int, p0: int) -> list[dict[str, object]]`; `collect.collect_traces(config_path: Path, split: str, out: Path, *, dry_run: bool = False) -> dict[str, object]`. Extend `LeaseOutcome` with snapshot/dispatch, selected-feature shard index, pool/support IDs, raw predictions, behavior propensity, local progress, body/admin/full duration, parent-available endpoint gain and natural-completion fields. Traces are array shards plus JSON metadata, not unbounded dict lists in memory.

- [x] **Step 1: Write failing propensity/support tests.** For pool size 2, two lengths, epsilon 0.2, heuristic action probability is approximately 0.85 and each other action 0.05; probabilities sum to 1. No filtered-out/unselected action gets a label. Unsupported length rejects. RNG replay reproduces action choices/pool hashes. Confirmatory/shift input cannot enter collection.

```python
def test_uniform_mass_also_counts_for_heuristic_action():
    heuristic = (NodeKey(1, 7), 1)
    p = mixture_probability(heuristic, heuristic, 2, 2, 0.2)
    assert p == pytest.approx(0.85)
    assert mixture_probability((NodeKey(1, 8), 1), heuristic, 2, 2, 0.2) == pytest.approx(0.05)
```
- [x] **Step 2: Write failing interval/censoring tests.** Entry 0, snapshot 2, dispatch 5, next rebid entry 20 gives administration 5 and body 15, with all costs retained. Receipt after a deadline is excluded from gain even if the worker's local utility increased. Deadline-truncated zero endpoint gain retains unknown natural-completion status; watchdog duration is a censored lower bound, not an ordinary training sample. Final empty/expired callback administration goes to residual cost, not nowhere.
- [x] **Step 3: Run red.** `python -m pytest tests/test_collection.py tests/test_lease_labels.py -q`; expected missing collector/label APIs.
- [x] **Step 4: Implement randomized collection and offline labels.** Start epsilon at 0.2; use dedicated recorded pool/behavior/solver streams, several declared fixed heuristic behaviors, and exact conditional mixture probabilities. The decision interval starts before frontier scan; continuation callbacks stay in body. Reconstruct gain from parent receipt records after each request; do not leak those future receipts into features. Preserve all zero gains, censored and failed attempts, selected features and support. Change epsilon only from training/validation support evidence, documenting it.
- [x] **Step 5: Verify and collect a bounded first shard.** Run both modules and `python -m ra.cli collect --config configs/exploratory.json --split train --out data/traces/train`. Expected validated supported actions, exact interval reconciliation, complete failed/censored records, and measured bytes/throughput/RSS forecast. Extend collection only to resolve observed support or learning-curve uncertainty, not a fixed paper-sized dataset.
- [x] **Step 6: Commit.** Stage collection/label logic/tests/CLI and declared training protocol; commit `feat: collect randomized costed subtree investments`. Keep raw large trace shards outside Git.

## Task 12: Gain/body models and closed-loop local bidder (WP04)

**Files:** Create `src/ra/models.py`, `src/ra/train.py`, `tests/test_models.py`, `tests/test_bidder.py`; extend `allocators.py`, `features.py`, `cli.py`, exploratory config; generate `artifacts/models/*` and model cards.

**Interfaces:** Produces `PredictionBatch(gain, body_seconds, body_q90)` arrays aligned with `FeatureBatch.actions`; `ModelBundle.predict(batch: FeatureBatch) -> PredictionBatch`; `train.fit_models(config_path: Path, trace_root: Path, output: Path, *, dry_run: bool = False) -> dict[str, object]`; `LocalBidder.choose(...) -> Allocation` and `.observe(...) -> None` through Task 8 protocol. Model card contains schema/data/environment hashes, estimator/preprocessing, targets/censoring/weights, supported actions, validation choice, costs, and footprint.

- [x] **Step 1: Write failing preprocessing/model tests.** Validation extremes do not change training medians/scales; constant-feature scale equals 1; per-instance total weight is equal despite unequal lease counts; zero gains stay; censored duration is excluded from ordinary completed-body fitting and appears in sensitivity counts. Ridge and boosted regressors predict gain and body seconds directly; quantile model has independently evaluated observed tail coverage. Schema mismatch/NaN rejects, never hidden native fallback.
- [x] **Step 2: Write failing ranking/deadline tests.** With gain `(0.2,0.3)`, body `(0.05,0.2)`, administration 0.05, rank the first action by rates `(2.0,1.2)`. Negative gains clip only for allocation and remain raw in logs. A body q90 of 0.06 survives dispatch remaining time 0.1 regardless of administration already spent. If every action fails the tail filter, only length-1 actions remain; zero bids use the declared estimate/bound/fixed-length fallback; positive ties prefer shorter length then node number. Expiry during prediction requests stop, records cost, and starts no new lease.

```python
def test_total_cost_changes_bid_ranking(costed_two_action_case):
    bidder, context, nodes, lengths = costed_two_action_case
    result = bidder.choose(context, nodes, lengths)
    assert result.root == nodes[0].key
    assert result.seconds_prediction == pytest.approx(0.1)
```
- [x] **Step 3: Run red.** `python -m pytest tests/test_models.py tests/test_bidder.py -q`; expected missing bundle/training/bidder interfaces.
- [x] **Step 4: Implement lightweight models and batched policy.** Fit ridge and histogram-gradient-boosted squared-error gain/body models; optional boosted quantile duration. Use pilot-measured `c_min`, current rebid administration, and dispatch-time future-body filter. Freeze array/schema/dtype conventions and supported lengths. Do not evaluate hidden continuations. Benchmark model loading/inference/extraction/RSS and complete cold requests. Model selection uses closed-loop validation utility after all costs, not prediction loss alone.
- [x] **Step 5: Verify and fit the minimum complete bidder.** Run model/bidder/feature tests; `python -m ra.cli train --config configs/exploratory.json --output artifacts/models`. Select from recorded grids spanning cheap linear through modest nonlinear capacity; expand only for an unresolved validation frontier/capacity trend. Collect one training-only learned-behavior round and refit or report deployment-state shift; preserve every candidate/failed fit and independent fitted seed. Report support/gain/body/tail diagnostics by budget/family/censoring.
- [x] **Step 6: Commit.** Stage models/training/bidder/tests/config/compact cards; commit `feat: learn deadline-conditioned local gain and duration bids`. WP04 success is working supported prediction, not confirmed improvement.

## Task 13: Horizon attribution and pooled-context contender (WP04/WP05)

**Files:** Extend `src/ra/features.py`, `allocators.py`, `train.py`; create `tests/test_attribution_controls.py`, `tests/test_pooled_features.py`, initial `configs/mandatory_baselines.json`; add B3–B6 configuration entries and validation cards.

**Interfaces:** Produces `features.append_pooled_context(batch: FeatureBatch, schema: FeatureSchema) -> FeatureBatch`; `train.fit_control(control_id: str, config_path: Path, trace_root: Path, output: Path) -> dict[str, object]`. Control IDs/configs resolve B3 one-node, B4 separately selected fixed length, B5 estimate-node/adaptive-length, and B6 pooled critic without changing the underlying solver.

- [x] **Step 1: Write failing matched-control tests.** B3 action support is only length 1 and is refit in that regime; B4 cannot change its fixed length within a run and selects its best length only from validation; B5 always chooses the estimate-ranked node while learning length. Shared pool/caching does not change eligible native work or hidden solver settings. All applicable controls charge their actual extraction/model loading/scoring costs.
- [x] **Step 2: Write failing pooled-context tests.** Pool values `(1,3)` append mean 2, population standard deviation 1, minimum 1, maximum 3; missing fractions and frontier size are explicit. Pool statistics aggregate continuous node fields over unique candidate nodes, not repeated length rows; action-length features are not pooled. Missing-only fields have declared masks. B6 is named pooled tabular and never receives a literature algorithm's name.

```python
def test_pooled_context_does_not_duplicate_nodes_by_length(pooled_13_case):
    batch, schema, mean_column = pooled_13_case
    enriched = append_pooled_context(batch, schema)
    assert enriched.matrix[:, mean_column] == pytest.approx(2.0)
```
- [x] **Step 3: Run red.** `python -m pytest tests/test_attribution_controls.py tests/test_pooled_features.py -q`; expected absent control paths/context features.
- [x] **Step 4: Implement and tune controls.** Recollect/refit supported regimes as necessary within train namespaces. Evaluate matched capacity then best measured feasible capacity for B6. Cross ranking × horizon and include tuned native plunging. Share generic engineering/vectorization/early exits among applicable Python methods; leave compiled native alone. Tune B0/B1/B2 and learned controls until the recorded validation saturation/resource criteria are met.
- [x] **Step 5: Verify and audit fairness.** Run both tests and serial closed-loop validation; record every contender/config, training/tuning expenditure, teacher-free feature boundary, and strongest validation choice. Gains absorbed by a fixed lease, pooled feature, or generic optimization are attributed to that component. All-frontier diagnostics run at a feasible scale with the same ledger.
- [x] **Step 6: Commit.** Stage control/features/train/tests/config/cards; commit `feat: add matched horizon and pooled-context controls`.

## Task 14: Literature reproduction and claim-scope register (WP05)

**Files:** Create `baselines/cards/{labassi,mattick-mutschler,trgnn,deepbound,treecl}.md`, `baselines/patches/`, `baselines/parity_fixtures/`, `tests/test_baseline_register.py`; extend `configs/mandatory_baselines.json`, `config.py`, CLI `reproduce`. Add code under `src/ra/baselines/<method>/` only for an actually permitted port.

**Interfaces:** Produces a `BaselineCard` validated record with source/commit/license, original regime, changes, tensor/live-feature parity, exact hybrid handoff, tiny optimum/reproduction evidence, CPU costs, and one of `reproduced`, `adapted`, `approximation`, `blocked`, `reference_only`. `config.validate_baseline_register(register: dict[str, object], cards: Sequence[dict[str, object]]) -> None`. `reproduce --baseline ID --config PATH --out PATH [--dry-run]` is available only for a port with a pinned executable entry point.

- [x] **Step 1: Write failing register tests.** A blocked/reference-only/approximation card cannot support an unqualified named-method superiority claim; missing reuse terms block code/checkpoint reuse, not the core. A shared-build adaptation needs its own evidence/config ID. Required B0/B1/B3–B6 cannot disappear. Reproduced contenders cannot be excluded merely for outperforming the candidate. A claimed parity/reproduction needs hash-addressed evidence.

```python
def test_reference_only_method_cannot_be_counted_as_beaten(unavailable_baseline_claim):
    register, cards = unavailable_baseline_claim
    with pytest.raises(ValueError):
        validate_baseline_register(register, cards)
```
- [x] **Step 2: Run red.** `python -m pytest tests/test_baseline_register.py -q`; expected missing register validation.
- [x] **Step 3: Inspect and pin sources and terms.** Use the exact repository/paper links in spec §13. Record Labassi architecture/loss/depth weighting/teacher/candidate comparison and two-incumbent switch; inspect Mattick–Mutschler `SelectTree.py`, `feature_extractor.pyx`, old ABI/environment and 750-selection handoff; revisit TRGNN code/permission, DeepBound strong-branching setting, TreeCL primary access. Do not infer CPU infeasibility from original hardware.
- [x] **Step 4: Execute a gate per accessible contender.** First fixed-tensor CPU inference/backward/serialization and required aggregation/extractor operations; then native feature extraction and exact handoff; then tiny original-regime reproduction. Each permitted port gets its own red/green parity tests and commit before larger training. Separate original-regime settings and common-build adaptation. For two-incumbent switches test paper-faithful anchor counting and explicit validation-tuned anchor-aware adaptation, keeping the stronger adapted contender. Charge teacher solves, port assets/training/inference, and failed attempts.
- [x] **Step 5: Verify and lock baseline statuses and allowed claim.** Run register tests; reproduce every claimed fixture and record source lines/config hashes. Unsupported code/access/license/operator/resource/fidelity gates receive specific blocked evidence. Main core may proceed with B0–B6 and actual reproduced competitors; contemporary-learned superiority remains unresolved when appropriate. A paper-inspired control is labeled approximation.
- [x] **Step 6: Commit.** Stage cards/register/tests and only permitted pinned port patches/fixtures; commit `research: register reproducible learned contenders and claim limits`. WP05 ends with an executable or explicitly blocked disposition for every named contender.

Disposition: all five named contenders stop at documented access/permission/fidelity gates. CPU/tensor/live/tiny reproduction checks are explicitly not run; no executable port is claimed. Current core controls remain eligible. See `docs/superpowers/evidence/task14/task-14-report.md`.

## Task 15: Pilot variance, analysis design, and immutable freeze (WP06)

**Files:** Create `src/ra/freeze.py`, `src/ra/stats.py`, `tests/test_freeze.py`, `tests/test_design_calibration.py`, `protocol/confirmatory.md`, `configs/confirmatory.json`; extend `metrics.py`, `cli.py`; generate `artifacts/pilot/power_design.json`, `protocol/freeze.sha256`, protected manifests and run queue.

**Interfaces:** Produces `metrics.log_budget_weights(deadlines: Sequence[float]) -> list[float]`; `stats.calibrate_design(pilot_summary: Sequence[dict[str, object]], design: dict[str, object]) -> dict[str, object]`; `freeze.freeze_protocol(config_path: Path, out: Path, *, dry_run: bool = False) -> str`; `freeze.verify_protocol(digest_path: Path) -> dict[str, object]`. Freeze digest references a canonical manifest with all frozen fields and referenced asset hashes; self-digest fields are excluded from their own preimage. The protocol records which source commit is hashed; committing the frozen manifest does not change that source identity.

- [x] **Step 1: Write failing weights/design tests.** Deadlines `(1,4,16)` produce weights approximately `(0.25,0.5,0.25)`; unsorted/duplicate/nonpositive deadlines reject. Duplicating timing repeats does not double independent template count. Native observations shared across fits remain shared. Pilot resource simulation includes crossed fits/clusters and budget/method pairing; it never reads protected outcomes. Small-fit uncertainty is explicitly marked conditional/limited.

```python
def test_log_budget_weights_and_invalid_grid():
    assert log_budget_weights((1, 4, 16)) == pytest.approx((0.25, 0.5, 0.25))
    with pytest.raises(ValueError):
        log_budget_weights((1, 1, 16))
```
- [x] **Step 2: Write failing freeze tests.** Missing hardware/build/data/model/features/baseline statuses, sample/fits/repeats, budgets/weights, bootstrap/contrasts, watchdog/exclusions/resource forecast rejects. A protected outcome read before freeze rejects. Changed model/config/split/source hash rejects verification. Identical resolved input gives identical digest. Dry-run writes nothing. Future scientific mutation requires a new experiment ID and numbered amendment rather than overwriting the frozen manifest.
- [x] **Step 3: Run red.** `python -m pytest tests/test_freeze.py tests/test_design_calibration.py -q`; expected absent calibration/freeze APIs.
- [x] **Step 4: Calibrate using discovery/validation only.** Fit native cold completion/progress deadline scale, bootstrap Monte Carlo quantile stability, paired/template/training/timing variance, useful precision, and affordable sample/fits/repeats. Simulate clustered/crossed planning and measured time/RSS/storage with overshoot reserve. Resolve mandatory primary contrasts including B0/B1 and attribution/global controls; fix `B` and `alpha=0.05`. Record explicit lack-of-power limitations rather than arbitrary success thresholds. Freeze measured `K`, horizon grid, model/config choices, seeds, thread settings, grace, failures/exclusions, weights, and secondary guardrails.
- [x] **Step 5: Implement freeze and dry-report preflight.** Generate fresh protected template manifests mechanically under the selected population/split rules without solution/timing inspection. Store complete scientific manifest, canonical digest, immutable queue order and artifact references. `python -m ra.cli freeze --config configs/confirmatory.json --out protocol/freeze.sha256` fails until every required field and WP04/05 gate resolves. Run the report path on discovery fixture results; labels say dry-run and cannot be confused with confirmation.
- [x] **Step 6: Verify and commit.** Run both modules, validate all hashes and unresolved-field inventory, inspect dry-run report/failure rules, and compare predicted resources to available capacity. Commit protocol/config/freeze and compact power evidence with `research: freeze protected evaluation and uncertainty design`. Opening protected results is authorized only for the exact frozen experiment during Task 16.

## Task 16: Fixed serial confirmatory execution (WP07)

**Files:** Extend `src/ra/runner.py`, `worker.py`, `config.py`, `cli.py`; create `tests/test_confirmatory_execution.py`; write `artifacts/runs/confirmatory/*` and immutable operational status during execution.

**Interfaces:** Consumes verified Task 15 manifest and Task 8 `run_schedule`. Produces `runner.execute_frozen(digest_path: Path, out: Path, *, resume: bool = False, dry_run: bool = False) -> list[Attempt]`. It verifies scientific hashes before launch and records actual operational attempts without mutating the protocol. Confirmation requests are independent runs for each deadline.

- [x] **Step 1: Write failing execution tests.** One worker at a time; order matches frozen block seed; every method/deadline/template/repeat/fit request is scheduled as registered, without multiplying shared native runs by fit count. A short-budget request loads its own conditioned config rather than truncating the long run. Resume rejects changed hashes; unfavorable/timeout/OOM records remain; simulated significance cannot change queue size/order. External interruption reruns an entire affected paired block only under frozen rules, with prior costs visible.

```python
def test_frozen_execution_rejects_changed_model(changed_frozen_model, tmp_path):
    with pytest.raises(ValueError, match="hash"):
        execute_frozen(changed_frozen_model, tmp_path)
    assert not list(tmp_path.glob("*/manifest.json"))
```
- [x] **Step 2: Run red.** `python -m pytest tests/test_confirmatory_execution.py -q`; expected absent frozen execution path.
- [x] **Step 3: Implement protected run enforcement.** Validate gates/digest, instantiate fresh workers/configs, randomize within paired instance/budget blocks exactly as frozen, and monitor resources/correctness without adjusting methods/population/sample. Correctness/resource alarms can stop and quarantine; no significance-driven stopping or silent fallback. Library/OS/source changes invalidate compatible reuse and require recorded recalibration/amendment.
- [x] **Step 4: Verify on artificial manifests.** Run execution/recovery/deadline tests; a tiny synthetic frozen fixture exhausts its exact queue and reconstructs records with no late utility or hash drift. This fixture is not the real confirmatory sample.
- [x] **Step 5: Execute the real frozen queue.** `python -m ra.cli run --config configs/confirmatory.json --phase confirmatory --resume`. Preserve every attempt, temperature/power/background/time-block metadata, last output and actual release cost. Do not inspect inferential significance to decide whether to continue. If the gate fails, retain evidence and narrow/report via Task 20.
- [x] **Step 6: Commit.** Commit runner/tests and compact immutable run manifest/operational progress with `feat: execute fixed serial protected comparisons`. Do not commit large raw traces; completion depends on actual request inventory, not the commit message.

## Task 17: Paired endpoints, uncertainty, and primary report (WP07)

**Files:** Extend `src/ra/metrics.py`, `stats.py`; create `src/ra/report.py`, `tests/test_metrics.py`, `tests/test_stats.py`, `tests/test_report.py`; extend `cli.py`; produce `results/confirmatory/{primary.csv,resource_summary.csv,confirmatory_report.md}` and standalone plot artifacts.

**Interfaces:** Produces `metrics.summarize_attempts(attempts: Sequence[Attempt], protocol: dict[str, object]) -> list[dict[str, object]]`; `stats.paired_frontier_intervals(summary: Sequence[dict[str, object]], protocol: dict[str, object]) -> dict[str, object]`; `report.analyze(config_path: Path, out: Path, *, dry_run: bool = False) -> dict[str, object]`. Summary rows identify template/cell/method/fit/repeat/deadline/frontier and status; no raw lease is an independent observation. Statistical output includes effects, ordinary and simultaneous intervals, conditional/across-fit qualification, and all registered contrasts.

- [x] **Step 1: Write failing metric tests.** Utilities `(0.2,0.4,0.8)` at weights `(0.25,0.5,0.25)` yield frontier 0.45. Parent receipt boundary, missing assignment, invalid-bound alarms, failures, population cell weights, and raw/tolerance-plot separation are pinned. A dual-only gain with worse primal is reported as a tradeoff, never a uniformly better decision.

```python
def test_frontier_uses_all_deadlines(three_deadline_attempts, three_deadline_protocol):
    rows = summarize_attempts(three_deadline_attempts, three_deadline_protocol)
    assert rows[0]["frontier"] == pytest.approx(0.45)
```
- [x] **Step 2: Write failing inference/report tests.** Identical method pairs give zero paired effect; constant candidate advantage 0.02 gives effect/interval endpoints 0.02. Cluster resampling keeps complete paired template budgets/repeats/methods and native results shared across independently resampled fits. Bonferroni per-contrast error is `0.05/B`; no registered contrast/status is dropped. Fixtures for positive/tight-negative/tight-null/wide-inconclusive effects produce distinct claim language. Few fits cannot produce an unqualified across-fit certainty claim.
- [x] **Step 3: Run red.** `python -m pytest tests/test_metrics.py tests/test_stats.py tests/test_report.py -q`; expected absent summary/inference/report APIs.
- [x] **Step 4: Implement reconstruction and analysis.** Aggregate per-template frontier, raw primal/dual/gap/solved/fault/resource curves, population weighting, and stratified template-cluster × complete-fit bootstrap. Preserve all shared observations; use frozen Monte Carlo stability rules. Quantile/mean regression calibration is limited to observed supported actions. Model/trace/training/tuning expenditure and censored counts appear separately. Save scientific plots with standard plotting tools; lock any new plotting dependency and distinguish analysis environment changes from solver environment.
- [x] **Step 5: Verify, then analyze once sample inventory is complete.** Run the three tests; rebuild each utility from immutable receipt traces and validate digest chain. `python -m ra.cli analyze --config configs/confirmatory.json --out results/confirmatory`. Expected every contrast/deadline/family/status shown, primary simultaneous claims limited to frozen tests, and raw resource totals including overshoot. The sample-complete check rejects partial primary analysis except an explicitly interrupted/blocked report.
- [x] **Step 6: Commit.** Stage analysis/report code/tests and compact primary summaries with `research: report costed paired solver effects and uncertainty`. Evidence determines positive, negative, null, or inconclusive wording.

## Task 18: Gated attribution, adversarial stress, and population parity (WP08)

**Files:** Create `src/ra/population.py`, `tests/test_population_parity.py`, `tests/test_robustness.py`, `configs/robustness.json`; extend analysis/control modules only for named treatments; generate `artifacts/equivalence/*`, `results/ablations/*`, and amendments when required.

**Completed scope:** Steps 2–6 were executed for the charged-latency diagnostic. The matched-population entry gate was checked and unmet; Step 1 and other matrix branches remain explicitly unexecuted, rather than pending.

**Interfaces:** Produces `PopulationAllocator` implementing Task 8 `Allocator` while sharing work/evidence and aggregating process-level mass; `population.couple(queue: Allocator, population: Allocator, cases: Sequence[dict[str, object]]) -> dict[str, object]`. Robustness config declares dataset namespace, candidate/control hash, varied component, fixed components, resource ledger, and whether diagnostic/exploratory/fresh-confirmatory.

- [ ] **Step 1: Write failing matched-representation tests only if its gate is met.** Identical kernel/work/RNG gives exact `(epoch,node,lease,completed_work,evidence_hash)` traces and output; cloning changes administrative copy counts, not evidence/bounds/estimates. Replication/merging/suspend/cancel/GC costs are timed. Independent-replica mode rejects unless both methods receive identical independent native states and charged costs. Cycle/spawn/cancel cannot manufacture credit.

```python
def test_coupled_population_has_same_work_and_evidence(coupled_cases):
    queue, population, cases = coupled_cases
    result = couple(queue, population, cases)
    assert result["queue_trace"] == result["population_trace"]
    assert result["queue_output"] == result["population_output"]
```
- [x] **Step 2: Write failing stress tests for selected discriminating treatments.** Delayed-result/latency injection is charged; random bids with matched inference latency and feature-shuffled models carry no privileged information. Larger horizon outside frozen support rejects. Beam consideration retains unselected native nodes. Rare-bridge misses are called missed optima only with known exact solutions. A changed trajectory cannot support a representation-only claim.
- [x] **Step 3: Run red.** `python -m pytest tests/test_population_parity.py tests/test_robustness.py -q` for implemented gated treatments; expected absent population/stress paths. Explicitly skipped engineering has a recorded gate reason rather than empty passing tests.
- [x] **Step 4: Implement the smallest discriminating experiments.** Use spec §12 matrix: ranking × duration/native plunging; gain/cost/q90; local/pool/global capacity; pool strata/cache/all-frontier; injected administration and rebid frequency; behavior support and instance versus lease weighting; independent fit stability; objective permutations/offsets; rare/expensive-bridge, restart, long-tail LP/deadline; cold/warm reuse. Share generic improvements. Matched population follows only a concrete time/memory question; core queue remains default.
- [x] **Step 5: Verify and interpret.** Require coupled parity before population timing. For every treatment store actual costs/support/uncertainty and attribute effects to changed components. Shifts are separate populations. An exploratory improvement or revised candidate/claim gets a numbered amendment, fresh protected templates, and another Task 15–17 sequence; original confirmation remains immutable.
- [x] **Step 6: Commit.** Commit each independently testable robustness treatment or matched representation milestone with descriptive messages; summarize with `research: attribute allocation effects and failure boundaries`. No escalation is justified solely by a favorable aggregate p-value.

## Task 19: Gated independent-set and real-instance transfer (WP09)

**Files:** Create `src/ra/transfer.py`, `tests/test_transfer_objectives.py`, `tests/test_transfer_manifest.py`, `protocol/transfer.md`, `configs/transfer.json`; extend `types.py` with domain-tagged original instances; generate transfer manifests/licenses/hashes/results.

**Closed disposition:** WP09 is skipped because the scientific entry gate is unmet. Step 1 was verified; Steps 2–6 and all transfer interfaces remain unexecuted, rather than pending. The disposition and evidence were committed separately.

**Interfaces:** Produces `transfer.generate_independent_set(config: dict[str, object], seed: int) -> dict[str, object]`, `transfer.independent_set_utility(primal: int, dual: float, total_weight: int) -> float`, `transfer.validate_manifest(manifest: dict[str, object]) -> None`; CLI `transfer --config PATH --out PATH [--dry-run]`. Domain-tagged solver inputs preserve original exact feasibility checker and separate metric adapter; set-cover `CoverInstance` is not overloaded silently.

- [x] **Step 1: Verify the entry gate before coding.** Require either meaningful primary benefit with attribution or a specific evidence-supported locality/scale prediction, plus source/license/storage/resource feasibility. Otherwise mark WP09 skipped with reason and go to Task 20. No obligatory full MIPLIB download.
- [ ] **Step 2: Write failing domain/license tests.** Weighted independent set uses empty primal anchor 0, upper bound `sum(w)`, exact positive weights/edge constraints, and utility `1-(dual-primal)/sum(w)`; empty progress has utility 0 and proven optimum has utility 1. Reject incompatible MIPLIB metrics from pooling with primary normalized set cover. MIPLIB selection is based on frozen metadata criteria, never candidate performance. Unclear redistribution terms prevent bundling; known optima cannot enter runtime features. Frozen zero-shot and retrained tracks have separate model IDs/costs.

```python
def test_maximization_progress_reverses_primal_dual():
    assert independent_set_utility(0, 10, 10) == 0.0
    assert independent_set_utility(4, 6, 10) == pytest.approx(0.8)
    assert independent_set_utility(6, 6, 10) == 1.0
```
- [ ] **Step 3: Run red.** `python -m pytest tests/test_transfer_objectives.py tests/test_transfer_manifest.py -q`; expected absent transfer APIs.
- [ ] **Step 4: Implement one domain track at a time.** Add weighted independent set's original verification and maximize-space conversions, with tiny enumeration. For MIPLIB inspect only needed archive contents/terms/space, pin hashes, and preselect compatible binary covers from metadata. Retain failures/timeouts. Adopt native/domain strongest controls, prospectively calibrated local pilot and domain-specific budgets/metrics before transfer freeze. Separate teacher/evaluation optima.
- [ ] **Step 5: Verify and execute the separately frozen transfer.** Run both modules and tiny native objective/lifetime tests, then `python -m ra.cli transfer --config configs/transfer.json --out results/transfer`. Report synthetic/domain/zero-shot/retrained results separately; changes require their own amendments. Scope claims to actual shifts/domains.
- [ ] **Step 6: Commit.** Stage transfer code/tests/protocol/config/compact permitted manifests/results; commit `research: evaluate gated allocation transfer with separate metrics`.

## Task 20: Scope-correct final report and clean reproduction (WP10)

**Files:** Extend `src/ra/report.py`, `cli.py`, `tests/test_report.py`; create or update `REPORT.md`, `CLAIMS.md`, `REPRODUCE.md`, `MANIFEST.sha256`, `README.md`, `PROGRESS.md`, `DECISIONS.md`, cards and archive manifest. This task also handles a valid early stop before learning or confirmation.

**Interfaces:** Produces `report.build_report(manifest_path: Path, out: Path, *, dry_run: bool = False) -> dict[str, object]`; CLI `report --manifest PATH --out PATH [--dry-run]`. For completed confirmation, manifest is `protocol/freeze.sha256`; early-stop reports use a clearly labeled achieved-scope manifest with no fabricated freeze/sample/model fields.

- [x] **Step 1: Write failing report/reproduction assertions.** Analytical-only or blocked capability fixture cannot claim solver gain; validation-only fixture cannot claim confirmation; a blocked contemporary comparator cannot be called beaten. Every failed/negative/null/inconclusive package appears. Headline rows include exact competitors/population/template/fit/deadline/interval/primal/dual/resources/training/claim/caveat fields. No unavailable original brief/chat history is needed to reconstruct a table.

```python
def test_analytical_only_report_has_no_empirical_solver_claim(analytical_manifest, tmp_path):
    output = tmp_path / "REPORT.md"
    result = build_report(analytical_manifest, output)
    assert result["empirical_solver_claims"] == []
    assert "not executed" in output.read_text().lower()
```
- [x] **Step 2: Run red.** `python -m pytest tests/test_report.py -q` for new report cases; expected failing scope/completeness assertions before implementing final report path.
- [x] **Step 3: Implement and generate the handoff.** `python -m ra.cli report --manifest protocol/freeze.sha256 --out REPORT.md` for full confirmation, or the achieved-scope manifest for early stop. Include exact locks/native/source revisions, all amendments/attempt costs/licenses/access gaps, dependency/API limits, and commands to regenerate summaries. Distinguish methodological distinction, measured improvement, and practical value. Show break-even reuse only for measured positive matched-quality time savings; otherwise separate cost/utility reuse curves. Negative/blocked results are complete valid outcomes within achieved scope.
- [x] **Step 4: Reproduce from a clean local environment.** Install the locked artifact set using its hashes, verify native binary/config parity, run the required analytical/native tests, rebuild primary tables from immutable artifacts, and run a measured small independent solver rerun within the achieved scope. Compare table hashes/numerical tolerances. No second machine or remote service is needed; do not turn a fresh OS/library environment into an unrecorded scientific revision.
- [x] **Step 5: Verify completion.** Run tests appropriate to the implemented scope, `python -m pip check`, report/manifest validation, score reconstruction, and `git diff --check`. Reconcile requirement coverage against spec §§1–13, clarify unexecuted/skipped/blocked packages, and verify no runtime privileged continuation, post-deadline gains, dropped costs, inflated independent units, or unqualified baseline aliases. Do not broaden/repeat testing after passed required checks without a new concern.
- [x] **Step 6: Commit.** Stage final report/reproduction/claims/compact manifests and code/tests; commit `docs: publish reproducible allocation findings and limits`. Preserve current branch; merging, deployment, and pushing are outside this implementation plan unless separately requested.

## Coverage and planning handoff

| Specification area | Owning task and decisive check |
| --- | --- |
| §1–2 scope, evidence/claim boundaries and hypotheses | 3, 9, 13–20; analytical parity, headroom gate, registered contender/claim tests |
| §3 exact output, receipt deadline and cold costs | 5–7, 11, 17; original integer check, delayed receipt, startup timeout, disjoint ledger |
| §4 architecture and immutable ownership | 1–2, 5–8; runnable package, typed primitives, current live mapping, hashes |
| §5 native lifecycle, leases and credit | 2–4; real restart/deletion/completion capability, lease and conservation tests |
| §6 pool/features/costed policy | 4, 10–12; candidate support, infinity masks, administration/body ranking and deadline filter |
| §7 recipes/splits/randomization/censoring | 5, 11–12; canonical seed lineage, propensity, observed endpoints and completed-duration fitting |
| §8 baselines/tuning/reproduction | 8–9, 13–14; native overrides, separately trained controls, pooled and literature parity/cards |
| §9 primary endpoints/statistics/freeze/amortization | 15–17, 20; log weights, clustered/crossed design, protected hashes, scoped intervals |
| §10 ordered gates and measured resources | 1–20; entry gates, artifact authority, forecast/stop/recovery decisions |
| §11 commands/records/atomic failure handling | 1, 3, 5–8, 11–12, 14–17, 19–20; help/dry-run/validation, immutable attempts and hash-safe resume |
| §12 robustness/transfer/report contract | 18–20; matched treatments, fresh confirmation, separate domains and clean reproduction |
| §13 and Appendix A self-contained provenance | 3, 14, 20; faithful copied diagnostic, pinned optional sources and no hidden requirements |

Planning self-review: each task has an owned deliverable, named files/interfaces, red/green checks, and a commit boundary. Gate-dependent measured values are deliberately not invented. Before execution, read both documents and confirm the implementation scope; preserve the user's current-branch instruction. A native execution approach is a reasonable default for these tightly shared solver/observer interfaces if implementation is subsequently requested; independent scientific/parity reviews still apply at the gates. This delivery ends at spec and plan.
