# Progress

Updated: 13 October 2026.

Current stage: WP00 environment/native capability gate passed after independent review and fresh target verification; Task 3 / WP01 administrative and analytical diagnostics implemented and locally verified, pending independent review. Current branch: `main`, preserved from the initial empty checkout.

## Completed documentation

- Self-contained [specification](docs/superpowers/specs/2026-10-13-reasoning-allocation-design.md), including the complete supplied analytical reference and bounded claim rules.
- Superpowers builder check: a fresh reviewer found missing external authority and a missing diagnostic procedure. Both were resolved in the spec; the follow-up returned “nothing important left.”
- [Implementation plan](docs/superpowers/plans/2026-10-13-reasoning-allocation.md): 20 tasks, 119 unchecked execution steps, 20 representative test examples, and coverage of every specification section and WP00–WP10.
- Planning self-review: file ownership, shared interfaces, requirement coverage, failure cases, task dependencies, and experimental gates checked.
- Documentation verification: Markdown whitespace/fences, relative document links, task structure, test-example syntax, and analytical-reference syntax checked. These checks execute no solver experiments or product tests.

## Execution status

WP00: **passed**, with Task 1 environment/native-smoke and Task 2 lifecycle checks reviewed and verified. Actual hardware is Apple M3 Max, native ARM64, 36 GiB RAM, 14 logical CPUs, macOS 26.7.1; Python 3.12.9. PySCIPOpt 6.3.0 links SCIP 10.0.2 / SoPlex 8.0.2 and solves the tiny cover at independently checked objective 2. The exact 14-wheel dependency lock is committed; private discovery, install, wheel metadata/license, parameter and cost artifacts remain ignored.

WP01: **running**, with Task 3 administrative and analytical checks implemented and locally verified; remaining native correctness/harness requirements are pending. WP02–WP10: **not started**. No lease collection, fitted allocation model, frozen confirmatory experiment, or measured allocation comparison exists.

Task 2 exercises 11 native operations, including a real restart 1→2 with root-number reuse, primitive/callback-local node ownership, completed-node/deletion accounting, objective-space checks, cooperative stop, native release, and local clock comparability. Full suite: 49 passing tests. A fresh target doctor on commit `6f0cc10` passed; raw evidence is retained in `artifacts/environment/wp00_gate/doctor.json` and `artifacts/environment/capabilities.json`.

The terminal propagation-only root reports one native node and no completion-mask event; selected no-LP descendants reconcile in the exercised fixture. Both counters remain visible. Callback-enabled callers must use `ScipBackend.optimize()` or check `raise_if_failed()` after direct native operations. Original faults are preserved and native cleanup is safe in tested paths.

Task 3 **locally measured check**: the complete supplied [Appendix A procedure](checks/validate_design.py) reproduced 512 seeds and 102,400 matched queue/population decisions; budget and evidence checks passed. Delayed payoff reproduced 0.6 versus 1.0 with optimal path `BB`; duplicate-evidence arithmetic reproduced 0.8 versus 0.9411764705882353. Overhead ratios 1.12/0.84 remain illustrative algebra, not hardware timings. The added anti-lease fixture yields 0 for a two-step B lease versus 1 for path `AB`.

The [credit ledger](src/ra/ledger.py) conserves integer credit across split/merge/spawn/cancel cycles and rejects closed-lineage spending, duplicate IDs, repeated returns, and overdrafts. Four additional coupled seeds each retain 40 canceled zero-mass records, match 20 decisions and immutable evidence hashes, and finish at available/reserved/spent 800/180/20. Synthetic evidence `e1` remains posterior 0.8, bound 2, estimate 3; these are fixture values, not measured native progress. This ledger defines no global native stopping limit.

Focused Task 3 suite: 36 passing tests. Final full suite: **85 passing tests in 5.57 s** (49 existing, 36 added). Both direct Appendix A and `ra check --suite analytical` passed; unsupported suites/phases and Python assertion-disabled mode fail explicitly. Cold diagnostic subprocess wall times were 0.433 s (reference) and 0.449 s (CLI), retained with CPU/RSS scope and hashes in ignored `artifacts/checks/`; they are diagnostic resource costs, not allocation performance comparisons.

## Next entry gate

Review Task 3 and continue WP01's remaining native correctness and honest-harness gates using the locked environment. Follow the current-branch instruction and commit each tested milestone. Do not start training before the native capability, correctness, honest-harness, and headroom gates pass.

Early blocked or low-headroom outcomes proceed to the achieved-scope report in Task 20; they do not require building the optional population or transfer tracks.
