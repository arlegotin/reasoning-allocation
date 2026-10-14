# Task 15 / WP06: pilot design and immutable protected freeze

**Status: DONE_WITH_CONCERNS.** The active untouched design is **ra-wp06-e003, amendment A002**, at `protocol/freeze-A002.sha256`, using `configs/confirmatory-A002.json` and `protocol/confirmatory-A002.md`. The original e001 freeze at the brief's requested `protocol/freeze.sha256` is preserved unchanged. All three strict-verification paths pass; e002/A001 is also preserved. No protected solutions, traces, timing or outcomes exist or were opened.

Implementation commits: `34aca3d` (crossed planning, stable append and freeze APIs) and `baa66eb` (public trace capacity, stratified resource forecast, and freeze preflight/history corrections). The source commit actually hashed and measured by the active freeze is **baa66ebb247c3b272033066f3f2708b19977a47e**; later evidence commits do not change that source identity. Work stayed on current main, with one writer, no helper agents/worktree, no author contact and no publication. Root retains independent review and Task 16 dispatch.

## Implemented contract and named dependencies

`metrics.log_budget_weights`, `stats.calibrate_design`, `freeze.freeze_protocol` and `freeze.verify_protocol` implement the requested interfaces. CLI `freeze`, `verify-freeze` and a plainly labelled public `report` path are installed. Canonical manifests exclude their own digest; identical resolved input has an identical digest; dry-run creates no files; exclusive publication prevents overwrite. Missing scientific fields, prior protected access, malformed/duplicate/incomplete queues or cohorts, model/config/split/schema/status/source/environment drift and unresolved current method faults reject. References include 1000+ actual preflight/config/model/data assets. Config and manifest files are immutable by API and content verification, not a claim of filesystem write protection.

The malformed-ID Task 14 Minor was reproduced and fixed: type validation now precedes ID set construction, returning the normal validation error rather than an uncaught list-ID TypeError. The runtime source inventory previously omitted imported baseline subpackages; it now hashes recursive Python sources, with a regression proving `baselines/register.py` is included. Historical `6db9b038...` is not asserted to be the current executable.

`data.generate_indexed_workload` adds a named stable append interface. Tests compare old 0–11 input bytes, hashes, template/cell IDs, indices and lineage before and after extension. The old cell-major two-per-cell prefix remains unchanged; later rounds append one original per cell. Existing master/splits/population are preserved. The protected input cohort is generated mechanically from this mapping, after merging public split ownership; no solver is used in generation. The Task 9 duplicate/incomplete ranking helper was not reused. Owned summaries reject missing/duplicate template × method × fit × budget × repeat keys.

## Public evidence and actual deployed controls

Generation 1 measured 12 originals (two in each of the six locked cells), two timing blocks, seven physical methods and three separate deadlines: **504 physical attempts**, with 345 complete, 157 deadline and **two implementation errors**. Both errors were B3 on the same newly included hard original at the longest budget: the bounded learned trace reached 512 decisions at about 7.227 seconds. The failed attempt used approximately 18.52 MB and 162.40 MB peak RSS. Every original attempt, partial/censored indicator, raw progress and cost is retained under `artifacts/task15`.

After that fixed cohort completed, systematic debugging and RED/GREEN checks raised the explicit common learned telemetry capacity to 1024 decisions, while retaining a bounded writer and all selected scientific/model fields. This is recorded in every applicable method config and the freeze's telemetry overlay. The canonical old baseline register is untouched. No fallback or omission converted the failures into successes. Current B3 reached **841 decisions**, demonstrating that the correction was exercised rather than merely configured.

Generation 2, on committed `baa66eb`, reran the same complete 504-request public design, with source/config/order pinned before launch. It produced **347 complete and 157 deadline**, no implementation errors, no censored attempt durations, no missing wall/RSS/storage/overshoot fields, and confirmed resource release on all requests. No source edits, fitting or tests overlapped either serial timing generation. There were **12 unique pilot templates total**, not 24 from two source generations and not 1008 from physical attempts. No new training collection or fits occurred in Task 15. The deployed bundle contains one frozen set of existing assets, trained on 12 originals; deterministic fit-seed exports 17/43 remain aliases. Training-procedure variability is **unidentifiable**, not zero or demonstrated stable.

A remains the matched-data adaptive local ridge model (`8aca421a...`), preserving adaptive node/horizon allocation. B0 is default SCIP, B1 the registered tuned no-plunge setting, B2 the selected estimate/length-1 policy, B3 the regime-fitted one-node ridge, B5 the estimate-constrained histogram-7 duration policy, and B6 the matched pooled ridge. B4/length-1 is a verified logical alias of B3, with one shared physical outcome/contrast. There are **six unique primary contrasts**: A versus B0, B1, B2, B3/B4, B5 and B6. The historical local asset remains distinct. A/B6 supports matched-data, matched-ridge locality attribution; B5's differing capacity/regime prevents a pure causal node-choice interpretation. Five named literature contenders remain blocked with unrun fidelity/resource gates; none is called defeated or hardware-infeasible. No fixed-control win is renamed an adaptive success.

## Calibrated design, uncertainty and capacity

The active design fixes **60 protected originals, ten per cell; one frozen fit bundle; two timing repeats; 2520 physical requests**. Family masses are 1/3, with equal easy/hard mass per family: designed research prevalence, not industry prevalence. Solver seed 17 is shared across timing repeats; all native/shared observations retain the correct pairing and are not cloned as independent fit observations.

The native public means at 0.526707240 / 2.106828958 / 8.427315832 seconds are 0.987992 / 0.997126 / 0.999451, with completion fractions 50% / 79.2% / 91.7%. Eleven of 12 originals completed both longest-budget requests. The 0.180-second median completion is easy/startup dominated; retaining T0≈2.107 seconds preserves the observed hard progress and long-budget completion scale. Exact log-trapezoid weights are `[0.2499999999144038, 0.5, 0.2500000000855962]`; ideal 1/4,1/2,1/4 values are only approximate because deadlines are rounded integer nanoseconds. K=128, horizons 1/2/4/8/16/32/64, invocation floor 42 ns, model/schema choices, native/numerical thread settings and 2-second watchdog grace are pinned. The floor is not inference latency; the separate 2*T0 training intervention is not a primary deadline.

Useful conditional half-width 0.001 was prospectively chosen relative to the earlier measured native frontier headroom, not as a required effect or success threshold. Current public A−B0 is −0.0000850 and A−B1 +0.0001575. Timing SD means for those paired contrasts are 0.0001360 and 0.0007488; hard-cell paired-template SDs extend to about 0.00359. Easy-cell zero variance is reported as observed, not proof of population certainty. No adaptive superiority claim follows from these public results.

Final empirical simulation at 65,536 repetitions gives the following **conditional sensitivity**, not a power guarantee:

| Originals | Physical requests | Reserved minutes | Reserved artifact GB | Worst empirical simultaneous half-width | Conservative bounded half-width |
|---:|---:|---:|---:|---:|---:|
| 12 | 504 | 18.3 | 1.68 | 0.001039 | 0.956 |
| 24 | 1008 | 36.6 | 3.36 | 0.000804 | 0.676 |
| **60** | **2520** | **91.4** | **8.39** | **0.000510** | **0.427** |
| 120 | 5040 | 182.8 | 16.79 | 0.000363 | 0.302 |
| 240 | 10080 | 365.7 | 33.58 | 0.000258 | 0.214 |
| 600 | 25200 | 914.2 | 83.94 | 0.000163 | 0.135 |

N24 is the smallest tested option meeting the empirical 0.001 target for every primary contrast, but controller Ruling7 selects N60: ten independent originals per cell provide more informative within-cell uncertainty than four, with affordable expected precision improvement. The additional reserved cost is 3291.014 seconds (54.850 minutes) and 5,036,440,320 bytes over N24. The initial one-hour/20 GiB assumptions were not user constraints; larger alternatives were evaluated. Increasing N cannot repair one-fit uncertainty or identify unseen tails from two public originals per cell. A bounded simultaneous 0.001 guarantee would require approximately **10.96 million independent originals**, locally impractical. Accordingly this is an explicitly narrow, potentially inconclusive conditional evaluation. Repeats do not inflate N; there is no significance stopping or protected tuning.

The bootstrap preserves stratified template clusters, methods/budgets/repeats, complete crossed fit runs and shared native observations. Conditional intervals are available; across-fit intervals and fit variance are null/unidentifiable. Alpha is 0.05, B=6, ordinary quantiles .025/.975, simultaneous quantiles .05/(2B) and 1−.05/(2B). Initial observed-pilot quantile batches were discretely identical at 4096 draws. An additional planned-N check over four independent Monte Carlo seeds found endpoint ranges 7.6201e−5 at both 4096 and 16384, exceeding the fixed 5e−5 tolerance; **65536** reduced the maximum to 3.5266e−5. Preliminary artifacts remain intact; the stronger planned-N result determines the bootstrap count. At final N60, four seeds (2026101502–2026101505) with 65,536 draws have maximum endpoint range **1.1610639e−5**, below the same 5e−5 tolerance. The N60 worst empirical half-width is 0.000510213 and the bounded sensitivity is 0.427420.

Resource forecasts use maxima within each cell/method/fit/budget, preserve timing/fit counts, and add a **1.5 operational reserve**, not statistical confidence. Hardware is Apple M3 Max, 14 cores, 36 GiB physical memory, arm64 macOS; the preparation snapshot showed about 86 GB free disk, AC power/100% battery. Thermal/background isolation was not established. The selected storage forecast is about 8.39 GB, far below available space; the N600 storage option nearly consumes available disk.

**Pre-outcome amendment A001:** final reconciliation found the provisional 1 GiB coordinator allowance below measured coordinator peak 1,667,350,528 bytes. The e001 freeze was already sealed, so it was preserved rather than edited. A001/e002 explicitly reserves 8 GiB for the coordinator: a single 1008-request queue can be four times a measured 252-request pilot batch; fourfold observed peak is about 6.67 GB, rounded upward. Together with 4 GiB OS reserve and twice observed worker peak, the joint allowance is **13,416,628,224 bytes**, below **38,654,705,664 physical bytes**. This remains an operational assumption, not a guaranteed peak bound. Source/model/statistics/sample choices are unchanged; the same 24 mechanically generated inputs are explicitly reused unopened, under a new queue experiment identity.

**Pre-outcome amendment A002 / controller Ruling7:** e001/e002 and all referenced assets remain intact. N60 uses a separate successor registry and manifest snapshot, with the first 24 instance/template/cell/index/content hashes asserted identical, plus 36 freshly appended originals. All remain unsolved/unopened. The original per-template population mass changes from 1/24 to 1/60 in the new manifest. A new e003 queue has 2520 requests. The coordinator allowance becomes 20 GiB: ten times the measured 252-request peak is 16.6735 GB, rounded upward. With 4 GiB OS and twice measured worker RSS, joint allowance is **26,301,530,112 bytes**, below 38,654,705,664 physical bytes. Current free disk is 85,029,974,016 bytes. These are reserves, not guaranteed bounds. No methods, models, fitted bundle, source, deadlines or bootstrap count changed. The final design remains conditional and potentially inconclusive.

## Measured costs, failures and unknowns

| Measure | Generation 1 | Generation 2 |
|---|---:|---:|
| Inclusive batch wall seconds | 594.347 | 585.299 |
| Request wall incl. publication seconds | 586.062 | 576.972 |
| Worker CPU seconds | 536.395 | 527.307 |
| Parent CPU excl. publication seconds | 41.639 | 40.609 |
| Batch coordinator CPU seconds (overlapping scope) | 61.086 | 60.597 |
| Publication wall seconds | 12.247 | 12.363 |
| Overshoot seconds | 11.288 | 11.257 |
| Complete artifact bytes | 646,817,604 | 676,882,637 |
| Coordinator peak bytes | 1,670,774,784 | 1,667,350,528 |
| Maximum learned B3 trace decisions | 512 (fault) | 841 |

These scopes overlap and must not be naively added. The two source generations total 1008 physical pilot requests and 1179.646 seconds of inclusive batches. Failed attempts remain included. Raw attempt duration-censored flags are false for both generations, despite the trace-limit error's conservative unfinished-lease message. Every request's finalization/release/publication and raw statuses remain available in the hashed audit artifacts. Per-method counts, CPU, wall, memory, storage, release and overshoot are in `docs/superpowers/evidence/task15/task15.json`.

The extra planned-N Monte Carlo diagnostic used 0.926 wall/CPU seconds and 106.8 MB process peak; the larger design-grid recomputation used 3.419 seconds and 1.186 GB peak, after timing ended. The A002 N60 four-seed diagnostic adds 1.019 wall /1.018 CPU seconds and 144,506,880-byte process peak. Regenerating the stable prefix and adding 36 inputs costs 0.886 wall /0.885 CPU seconds, with 158,269,440-byte process peak. These preparation costs include no protected solving. New model-fitting/training cost here is zero. Historical training/tuning/capacity/failure costs remain in the unchanged Task 13/14 reports, model cards, register and referenced evidence; they are not erased or subtracted from runtime.

Known unsuccessful operations: the first hardware preparation was sandbox-denied on read-only CPU-brand sysctl; its generated public inputs are retained under `artifacts/task15-prepare-failed-sysctl`, and an authorized escalated retry succeeded. Generation-1 summary initially rejected every design because storage forecast used one maximum artifact for all slots; a hand-derived regression exposed the overgeneralization and the forecast was corrected before generation 2. One scoped pytest command named nonexistent `test_runner_faults.py`/`test_metrics.py` and ran no tests; the actual harness module was then used. Initial experiment-script compilation caught an unmatched parenthesis before source commit/timing. Freeze dry-run correctly rejected idealized weights on the rounded grid; the draft is preserved and exact weights were resolved before sealing.

Preparation/test command CPU and peak RSS, failed initial hardware-preparation CPU/RSS, summary reconstruction overhead outside the instrumented simulations, final report-writing tails, publication CPU tails and future thermal/background/storage/time extremes remain unmeasured. No remote GPU, LLM, paid inference, second machine or PyTorch was used for the core.

## RED/GREEN and verification actually run

Initial `.venv/bin/python -m pytest tests/test_freeze.py tests/test_design_calibration.py tests/test_generators.py tests/test_baseline_register.py -q`: **14 failed / 74 passed**, exposing absent APIs, stable append and malformed register IDs. Follow-up RED covered full freeze envelopes, missing scientific fields, unopened access, queues and CLI. Integration exposed two incorrect existing-API calls (`FeatureSchema.hash`, `validate_run_config`), which were corrected before timing. A JSON-order regression failed with unequal cell counts, then passed after deterministic cell ordering.

First source milestone: **163 passed in 11.60 s** across freeze/design/generator/register/harness modules; script/source compilation and `git diff --check` passed. The later targeted REDs reproduced the bounded 512 limit, global-max resource overestimate, reset-amendment bypass, unresolved public faults and missing transitive preflight reference. Corrections passed **215 tests in 13.98 s** before generation 2. Final same scoped command passed **215 tests in 12.82 s**:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=1 .venv/bin/python -m pytest tests/test_freeze.py tests/test_design_calibration.py tests/test_collection.py tests/test_generators.py tests/test_baseline_register.py tests/test_harness_controls.py -q
```

No old solver grid or full-suite repeat was run. Both 504-request public pilots ran through `checks/task15_design.py prepare/pilot`, sequentially under committed source. Summaries hash-audited the complete public cohorts. Finalization packages the preserved 65536-draw design in a separate namespace, using the same committed packaging function; the exact namespace/entrypoint is in `artifacts/task15/finalization/packaging-command.json`.

The actual public report command succeeded and writes `DISCOVERY/VALIDATION DRY REPORT`, explicitly not confirmation:

```sh
.venv/bin/python -m ra.cli report --pilot-summary artifacts/task15/generation2/pilot-rows.json --design artifacts/task15/finalization/design.json --out artifacts/task15/finalization/dry-report.md
```

All three freeze dry-runs and real freeze/strict verification calls succeeded. Positive amendment behavior is exercised by the preserved e001 → e002 → e003 chain. Each still passes strict verification, archival envelope checks and committed-source inventory checks. All three protected outcome namespaces were checked absent. A002 artifact preparation and sealing entrypoint scripts are preserved under `artifacts/task15/amendment-A002/`, with hashes in durable amendment evidence. Future startup timeouts score zero; method/cap faults are retained zero-primary outcomes with costs and trigger halt/diagnosis; numerical alarms quarantine; only identical-request external-interruption retries are allowed. Missing/duplicate cohorts block complete inference. Budget-specific primal regressions are tradeoffs and secondary claims stay exploratory.

## Active hashes and downstream handoff

- Active canonical digest, e003/A002: `8597c9ef7f0046b7ded617439f9026de9bc957d23e06b6f224492d0ee2cf3d62`.
- Preserved e002/A001 digest: `9b8e9907f6b7d3fda31d05bfefe884dacb53b1cddc1c2278540cc541b627551f`.
- Original canonical digest, e001, retained: `9bf1e05c293ab936bc6cde4a9b585087e8c11ff24a33c87fa7609f30e9723aa6`.
- Active config bytes: `1c121eeffce07b8820f774300b539a8da5dc6261f32056dc5aaa1707ddc8077e`.
- Active queue bytes: `6990b0341848c1967778fcbf84ac1ab6980318661fc32cfa1ae7c6431ac21421` (2520 unique complete physical rows).
- Protected manifest bytes: `18c57e1ce37c1765dc833f23384bf9b96076bb592c393c0105e77ae6104b3ff0` (60 originals; no outcomes).
- Actual recursive source: `f5f1651d6f86626ed31162df6ae04a6d8e42eb2f087271bd6c8dc0d19313a7dd`.
- Environment: `581c89be8c1343d6f925483e82100f4fe81293fea771eedb21aac08a296c5329`.
- Native build: `090e514d7d7581d68bdd17d6880096b12008861c21e34fa31d3d2fa18803cbaf`.
- Final power/design artifact bytes: `d2d4307e0c4964451c89dcec840eb3af9ccf8b9a70903acc0873d4d6f70ba48e`.
- Model hashes: A `8aca421ab3a648b5555e0eee826094e2b073bf9cec1856bb22321f2a0b519d58`; B3/B4 `d89a46164b6393b294f154286ec45ee7bf0393d56d7f57ae2387c379142c9cd1`; B5 `21582df36842f18ba009d5023ba47fff1cbff7a54f84b8ebcfa4367b4d6d98eb`; B6 `7099323057239d4cafa9eb8417b2a06a076e1b18d1b9e6a4d9b2b52505a3d8e2`.

Exact feature/model/data/split/environment/queue/config references and statuses are in the canonical manifests. Durable evidence is `docs/superpowers/evidence/task15/`; latest amendment evidence is `amendment-A002.json`, with `design-selection-A002.json` carrying the final sample/capacity inventory. Earlier evidence remains distinctly named.

**Task 16:** public execution still refuses protected phases. Any protected-run wiring changes the live source identity. Preserve e001, e002 and e003 assets; create **A003 and a new experiment ID / untouched verified freeze before the first protected outcome**. Reusing the 60 inputs is permissible only while still unopened and explicitly declared in that amendment. Do not silently exempt runner/CLI/stats/reporting changes from source verification. Future outcome-informed scientific changes need appropriate fresh confirmation. The frozen empty access ledger is an at-freeze attestation; append actual protected-access events in a separate execution journal.

**Task 17:** retain `verify_protocol` as mandatory strict live-source/environment verification for launch/resume. Later analysis source changes do not rewrite what executed. Historical analysis/reproduction uses `verify_envelope`, the frozen committed-source inventory, and attempt/source/config/model/environment/build identity checks, while recording analysis code independently. `stats.calibrate_design` remains public-only; its dry report is never confirmation. Across-fit uncertainty remains unidentifiable, and no statistical or superiority claim is made by this freeze.
