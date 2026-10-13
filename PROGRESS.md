# Progress

Updated: 13 October 2026.

Current stage: WP00 environment/native capability gate passed after independent review and fresh target verification; Tasks 3–4 / WP01 administrative, analytical, lease and candidate diagnostics implemented and locally verified. Task 4's first review fixes await scoped re-review; WP01's Task 5 tiny exact correctness gate remains pending. The cold parent/worker request harness belongs to Task 6 / WP02. Current branch: `main`, preserved from the initial empty checkout.

## Completed documentation

- Self-contained [specification](docs/superpowers/specs/2026-10-13-reasoning-allocation-design.md), including the complete supplied analytical reference and bounded claim rules.
- Superpowers builder check: a fresh reviewer found missing external authority and a missing diagnostic procedure. Both were resolved in the spec; the follow-up returned “nothing important left.”
- [Implementation plan](docs/superpowers/plans/2026-10-13-reasoning-allocation.md): 20 tasks, 119 unchecked execution steps, 20 representative test examples, and coverage of every specification section and WP00–WP10.
- Planning self-review: file ownership, shared interfaces, requirement coverage, failure cases, task dependencies, and experimental gates checked.
- Documentation verification: Markdown whitespace/fences, relative document links, task structure, test-example syntax, and analytical-reference syntax checked. These checks execute no solver experiments or product tests.

## Execution status

WP00: **passed**, with Task 1 environment/native-smoke and Task 2 lifecycle checks reviewed and verified. Actual hardware is Apple M3 Max, native ARM64, 36 GiB RAM, 14 logical CPUs, macOS 26.7.1; Python 3.12.9. PySCIPOpt 6.3.0 links SCIP 10.0.2 / SoPlex 8.0.2 and solves the tiny cover at independently checked objective 2. The exact 14-wheel dependency lock is committed; private discovery, install, wheel metadata/license, parameter and cost artifacts remain ignored.

WP01: **running**, with Tasks 3–4 administrative, analytical, lease and candidate checks implemented and locally verified; remaining native correctness/harness requirements are pending. WP02–WP10: **not started**. No scientific lease collection, fitted allocation model, frozen confirmatory experiment, or measured allocation comparison exists.

Task 2 exercises 11 native operations, including a real restart 1→2 with root-number reuse, primitive/callback-local node ownership, completed-node/deletion accounting, objective-space checks, cooperative stop, native release, and local clock comparability. Full suite: 49 passing tests. A fresh target doctor on commit `6f0cc10` passed; raw evidence is retained in `artifacts/environment/wp00_gate/doctor.json` and `artifacts/environment/capabilities.json`.

The terminal propagation-only root reports one native node and no completion-mask event; selected no-LP descendants reconcile in the exercised fixture. Both counters remain visible. Callback-enabled callers must use `ScipBackend.optimize()` or check `raise_if_failed()` after direct native operations. Original faults are preserved and native cleanup is safe in tested paths.

Task 3 **locally measured check**: the complete supplied [Appendix A procedure](checks/validate_design.py) reproduced 512 seeds and 102,400 matched queue/population decisions; budget and evidence checks passed. Delayed payoff reproduced 0.6 versus 1.0 with optimal path `BB`; duplicate-evidence arithmetic reproduced 0.8 versus 0.9411764705882353. Overhead ratios 1.12/0.84 remain illustrative algebra, not hardware timings. The added anti-lease fixture yields 0 for a two-step B lease versus 1 for path `AB`.

The [credit ledger](src/ra/ledger.py) conserves integer credit across split/merge/spawn/cancel cycles and rejects closed-lineage spending, duplicate IDs, repeated returns, and overdrafts. Four additional coupled seeds each retain 40 canceled zero-mass records, match 20 decisions and immutable evidence hashes, and finish at available/reserved/spent 800/180/20. Synthetic evidence `e1` remains posterior 0.8, bound 2, estimate 3; these are fixture values, not measured native progress. This ledger defines no global native stopping limit.

Focused Task 3 suite: 36 passing tests. Final full suite: **85 passing tests in 5.57 s** (49 existing, 36 added). Both direct Appendix A and `ra check --suite analytical` passed; unsupported suites/phases and Python assertion-disabled mode fail explicitly. Cold diagnostic subprocess wall times were 0.433 s (reference) and 0.449 s (CLI), retained with CPU/RSS scope and hashes in ignored `artifacts/checks/`; they are diagnostic resource costs, not allocation performance comparisons.

Task 4 **locally measured check**: [leases](src/ra/leases.py) select the live root first, then its descendants by depth/estimate/bound/number, spend only distinct dispatch-owned main-tree completions, and return unused per-grant allowance once. Restart/ancestor deletion/cancellation/deadline close credit; a new incumbent and unrelated deletion preserve continuation. [Candidate pools](src/ra/candidates.py) retain ordered primitive IDs/hash/strata and replayable RNG state, including 32 unique slots under overlapping rankings; excluded nodes remain live. These mechanisms impose no global node stopping budget.

Repeated public diagnostic searches at lengths 1/2/8 each reproduced their own selected-node trace and exact ledgers. Their native/focus/completion/selection counts were respectively 24/24/24/24, 6/6/6/6 and 13/13/13/13. Actual restart 1→2 yielded 17 completions and 18 selections; old-root deletion canceled the first lease before the new native run was exposed. Completion-boundary timeout yielded one post-deadline completion, zero spent allowance and a legal live return while stopping; dispatch-boundary timeout yielded no completion. Diagnostic presolve/heuristic/separation overrides and every changed parameter are retained. The separate tiny normal-enhancement fixture solved in presolve and exercised no lease callback.

Lease body time runs from first dispatch through the supplied next rebid-entry/terminal boundary, including native work after the final credited completion. Successful continuation scan overhead is recorded separately within that body. Callback entry/end/dispatch and safe-return markers prepare Task 6 / WP02's downstream cold-request ledger. WP01 remains running until Task 5's generators and enumerated tiny exact audit pass.

Final Task 4 focused suite: **38 passed in 0.50 s**. Tasks 2–4 suite: **116 passed in 2.45 s**. Full suite: **123 passed in 5.53 s**. Eleven sequential native diagnostics in one cold child took 0.538 s with single native/LP/numerical-library threads; child CPU/RSS and one failed evidence-serialization attempt are retained in ignored `artifacts/checks/task4/`. These costs describe diagnostic verification, not allocation performance. The [Task 4 report](.superpowers/sdd/2026-10-13-reasoning-allocation/task-4-report.md) records RED/GREEN transcripts, counters, provenance, hashes and limits.

Task 4 **first review fix round**: invalid initial allocation roots now fail through native callback containment before policy dispatch. Known rebids close the prior outcome and record new administration before scanning; discovered rebids and uncertain scan faults retain explicit immutable boundary/residual records. Confirmed continuation faults remain in the prior body through safe return. Finalized outcomes remain available independently of a later successful policy callback. New focused regressions: **45 passed in 0.63 s**. Covering native lifecycle/smoke, ledger, lease and candidate tests: **107 passed in 1.37 s**. Seventeen separately labeled sequential diagnostic/negative cases took 0.608 s in one cold child; historical Task 4 artifacts retain their original hashes. No broader suite was repeated after covering verification; the 123-test full-suite result above is historical to the initial implementation.

## Next entry gate

Review Task 4 and continue WP01's remaining native correctness and honest-harness gates using the locked environment. Follow the current-branch instruction and commit each tested milestone. Do not start training before the native capability, correctness, honest-harness, and headroom gates pass.

Early blocked or low-headroom outcomes proceed to the achieved-scope report in Task 20; they do not require building the optional population or transfer tracks.
