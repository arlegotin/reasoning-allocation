# Task17 implementation and scientific analysis

Status: **DONE_WITH_CONCERNS** (ready for controller independent review). Base `ebe331e`. One writer, current main, no helpers/worktrees. No frozen input, queue, protocol, model or historical record changed.

## Implementation and TDD evidence

New APIs: `metrics.summarize_attempts`, `stats.paired_frontier_intervals`, `report.analyze`; new `analyze` CLI. Deadline rows retain template/cell/method/fit/repeat/status, raw primal/dual/gap, tolerance-only plotting gap, faults and resources. Frontier weights and independent cold deadlines are frozen. Inference resamples complete original-template clusters within cells and globally crossed genuine fits, sharing native outcomes; one actual fit has no across-fit interval. All six unique contrasts and the B4=B3 alias are retained.

Historical analysis uses immutable `verify_envelope`, the executed Git source inventory, committed Task16 audit/seal/operational references, every raw attempt/artifact hash, exact expected request/config/model/environment/build identity and independent original-space assignment verification. Raw complete-frame receipt records must match the parent journal. Later analysis code/environment identity is separately recorded; strict current launch guards remain unchanged.

RED commands used `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest ... -q`:

- Initial `tests/test_metrics.py tests/test_stats.py tests/test_report.py`: 18 failed, 1 passed. Expected absent APIs/report module and the inherited planning count1–3 empty-batch bug.
- Immutable reconstruction/report additions: 3 failed, 6 passed (absent reconstruction and analyze APIs).
- Resource/calibration/CLI additions: 3 failed, 9 passed (absent helpers and CLI command).
- Physical cost deduplication: 1 failed, 12 passed (absent project inventory helper).
- Self-review family/support regression: 2 failed, 17 passed. Actual generator lineage nests family inside `cell`; calibration requires observed support and receipt-rebuilt gain.
- GREEN after these changes: all 28 focused tests passed in0.17s.

Transcripts are in `docs/superpowers/evidence/task17/`. Hand-known fixtures pin frontier0.45, receipt equality versus late improvement, independent assignment infeasibility despite resealing, raw negative gap versus plot clipping, exact zero/±0.02 paired intervals, unequal cell weights, complete paired budget/repeat/method/fit integrity, shared native outcomes, all statuses, Bonferroni error, distinct claim classes, and a dual/primal tradeoff.

Standalone plotting smoke check on artificial data generated both scientific PDF/PNG figures. `matplotlib==3.10.7` and its dependencies are separately hash locked in `requirements/analysis-plot.lock`, installed only in `artifacts/task17/plot-env`. Initial cache-permission and sandbox DNS setup failures were retained as disclosed preparation costs with unknown elapsed tails; narrowly reviewed dependency download succeeded. The solver `.venv` was not modified.

## Verification and scientific result

Completed; see the final verification and scientific outcome below. The complete frozen inference ran once after the pre-inference metadata join correction.

## Cost and claim boundaries

Full retained project inventory counts physical attempt IDs once, including failures, partials and pre-fix generations, never cumulative prior costs. Worker sampled/exact CPU uses the maximum rather than their sum. Nested fit/driver/generation/tuning envelopes are separate overlapping evidence, not an exact project grand total. Task16 batch/request/coordinator/overshoot/trace scopes retain the accepted handoff boundaries. Task17 records its own analysis wall/CPU/memory/plot subprocess resources; final write, interactive, development, test and setup tails remain explicitly unknown.

Task15M1 bootstrap counts1–3 validation is corrected. Task9M2 is not reused and remains deferred final triage. Task16M1 orchestration maintainability remains deferred. The analysis report module has multiple closely related reporting responsibilities and warrants maintainability attention; it does not split files beyond the task brief. Historical adaptation specifically authenticates the reviewed A004 Task16 evidence and is not a generic future-cohort acceptance mechanism.

Final pre-analysis self-review caught a calibration target mismatch: allocation mean seconds includes administration, while q90 predicts body-only duration. RED `test_q90_targets_body_duration_and_deadline_censoring_is_retained` failed0.0vs1.0 as expected; the correction compares q90 against body time and retains deadline/lower-bound censoring. Focused GREEN:29 passed in0.19s. First full suite:755 passed in145.33s. Final full suite after this correction: **756 passed in149.09s**, clean, command `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=1 .venv/bin/python -m pytest -q`. Both full transcripts retained; no real protected execution was repeated.

## First historical pass: pre-inference metadata stop

Implementation milestone `cdfefe9` passed756 tests. The actual analysis invocation stopped before any scientific aggregation/inference with `calibration action outside observed support`. Root-cause inspection showed immutable initial decision preparation may be revised before actual dispatch. The observed label correctly matched the final dispatch, while the new analysis joined it to initial preparation. No frozen record or scientific rule was wrong or altered. The correction consumes the existing authenticated `collect.read_decision` final-dispatch join, preserving all support and prepared-record hash checks. A tiny artificial initial-length1/final-length4 regression went RED (1 failed,15 passed), then focused GREEN30 tests. The failed invocation produced no result directory or inference output; its partial reconstruction/preparation cost is disclosed separately with wall/CPU not fully instrumented. It must not be represented as a successful scientific analysis or hidden from total work.

Final-dispatch correction full verification: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=1 .venv/bin/python -m pytest -q` — **757 passed in143.32s**, clean. The final-dispatch helper already verifies the final prepared-record digest, fixed context/support fields, dispatched action and selected-feature alignment; its use changes only the analysis join, not runtime behavior or frozen observations.

## Frozen scientific analysis completed

On analysis source `42a0b88`, every2520 immutable endpoint and observed calibration action passed reconstruction, and the single fixed primary inference was persisted. Internal wall169.227504084s, CPU140.672316s, peakRSS2767126528bytes, reconstruction151.905907292s, plotting childCPU0.812156s. The external `/usr/bin/time -l` wrapper printed169.82s real/99.89s user/42.30s system, then returned1 because sandboxed `sysctl kern.clockrate` is unavailable. The analysis command itself printed `success:true`, and every output was saved. This wrapper telemetry failure does not justify recomputation. Internal accounting and the exact wrapper transcript are retained.

Post-run checks independently matched all artifact-index hashes,2520 unique endpoint IDs, and protected wall/workerCPU/parentCPU/trace/overshoot totals against the sealed Task16 operational audit. Analysis environment and native build hashes exactly equal the historical solver environment/build; analysis source differs as required. Full retained project inventory contains9113 distinct physical attempts and ignores7 duplicate copies. No cumulative prior costs are added.

Frozen simultaneous results: A–B0 −0.0009064855530258782 [−0.0020026598875891523,+0.000027574589489313432]; A–B1 +0.0006065083267117086 [−0.0004928506394354197,+0.0018135692829494173]; A–B2 −0.0016836683476519694 [−0.0027070604003166673,−0.0006838331156158566]; A–B3 −0.0001077249188 [−0.0007718153164298796,+0.0006529927233088936]; A–B5 −0.0002285945105 [−0.0008677190507143456,+0.0004080793995589306]; A–B6 +0.000384038904 [−0.0001803361359106237,+0.0012546774633990564]. Exact unrounded values remain in the numerical artifacts.

No registered positive superiority result. Negative conditional frontier result against B2; native and remaining directional comparisons inconclusive. B6's four-batch upper-endpoint range0.00006025664962491578 exceeds the frozen0.00005 tolerance; all other diagnostics pass. Draws65536/seed2026101502 remain unchanged. One genuine fit, designed population only; no transfer/training robustness claim. Population-weighted endpoint utilities span0.9685536015568184–0.9997448286835815, near the ceiling.

## Interpretation-only correction after controller checkpoint

Initial output used 'descriptive tight-null' for B3/B5 relative to planning precision0.001. Exact prospective text in A002/A003 says this is a sensitivity target, not an effect-size or success threshold. Controller requested conservative labeling. The default classification now says direction inconclusive with a narrower interval around zero and no registered equivalence margin. Explicit declared useful-effect-scale fixtures remain separately scoped. Original inference bytes are preserved; every numerical primary field/hash stays unchanged. This is a claim/presentation correction, with no new inference, bootstrap, seed, model, threshold, population, deadline or raw reconstruction. Opposing primal/dual movements are explicitly exploratory tradeoffs, regardless of frontier direction. Paired per-budget/component point differences are derived solely from saved complete-cohort curves, without secondary intervals/tests.

Interpretation/support RED:8 failed,13 passed (new explicit scale API, frozen sensitivity-only regression, opposing guardrails and absent secondary effects helper). Focused GREEN:35 passed in0.19s. Final full-suite verification completed below.

Final interpretation-only full verification: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=1 .venv/bin/python -m pytest -q` — **762 passed in145.08s**, clean. This rerun was justified by the controller-requested default-classification correction and new paired-budget helper; no real primary inference was rerun. Both standalone scientific figures were visually inspected for legibility and raw/normalized axis labeling.


## Final deliverable and verification receipt

- Implementation: `cdfefe9` — feat: reconstruct frozen paired endpoints and inference.
- Historical final-dispatch join correction: `42a0b88` — fix: join calibration to final dispatched action. **Actual complete primary analysis source**: `42a0b88b08d6158629aa77d371d32cb6e433c4ad`.
- Conservative default interpretation and paired deadline reporting: `df9df35` — fix: keep precision targets separate from null claims. **Presentation-only source**: `df9df35403883458af9eee103093e820a7f3de71`.
- Results/evidence commit: recorded below after creation; no runtime/frozen scientific input changes.

The original numerical inference bytes are retained at `results/confirmatory/inference.original.json` (SHA256 `1a453a88c5a1834aa5d760f12157e0a564fa32b81613ea3ff37579a6dd56e22f`). Original and corrected primary numerical content has identical SHA256 `6339521bccab940fe0ec0546792a3c6012e65644fe7f63a5dde6418717b83d69`. Only B3/B5 interpretation strings changed. The presentation operation measured0.016459792s wall/0.012098s CPU after imports, excluding its final correction/index writes. It read saved curves only and generated180 exploratory scope/deadline/contrast rows (18 global, plus family/cell scopes). No inference/bootstrap/raw reconstruction was repeated.

Final independent saved-artifact check passed: all final artifact-index hashes; exact original/corrected numerical identity;2520 endpoints with1640 complete/880 deadline;60 original templates;18 global paired budget effects independently recomputed from saved physical endpoints for utility/primal/dual/raw gap; exact protected wall/workerCPU/parentCPU/trace/overshoot reconciliation; original indices12–71; unchanged solver environment/native build; strict CURRENT A004 launch rejects `current executable source/environment/build hash drift` as intended. Transcript: `docs/superpowers/evidence/task17/final-verification.txt`. The full337955-artifact operational audit was not duplicated: completed reconstruction authenticated each raw attempt chain once; final checks read compact outputs and metadata.

Final tests: **762 passed in145.08s**, clean. Focused35 passed in0.19s. Commands and all relevant red/full-green transcripts are retained in `docs/superpowers/evidence/task17/`. Scientific plot smoke checks and final visual inspection passed. No new study solver execution, fit, protected experimental repeat, seed selection, sample change, or deadline change occurred. Test-suite workers used isolated test fixtures.

Files changed: `src/ra/metrics.py`, `src/ra/stats.py`, `src/ra/report.py`, `src/ra/cli.py`; `tests/test_metrics.py`, `tests/test_stats.py`, `tests/test_report.py`; separate `requirements/analysis-plot.in`/`.lock`; verification transcripts/scripts in `docs/superpowers/evidence/task17`; compact CSV/JSON/report/PDF/PNG outputs under `results/confirmatory`. Large raw attempts/traces and the full project physical-attempt inventory remain local, hash referenced and preserved for final retention.

Final interpretation: no registered positive superiority; conditional negative A–B2; all other directional comparisons inconclusive. B3/B5 narrow intervals do not prove practical null/equivalence. B6's frozen Monte Carlo diagnostic fails and remains visible without extra draws. Raw primal/dual tradeoffs and budget effects are exploratory. One fit, designed population, near-ceiling utilities and uncertain tails constrain interpretation.

Remaining concerns: B6 numerical-stability limit; single-fit/population/headroom limits; unknown early/development/setup/failed-preparation/monitoring/publication tails and external timing-wrapper telemetry denial; historical analysis adaptation is A004-specific; report module size/maintenance; Task9M2 and Task16M1 deferred. Task15M1 is fixed. These are disclosed limits, not an incomplete cohort or unreported contrary outcome. Controller owns independent review; no reviewer/subagent was spawned.
