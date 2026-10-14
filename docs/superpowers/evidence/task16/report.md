# Task 16 — fixed serial protected execution (DONE WITH CONCERNS)

Base: `bdd0f39`. Scope: Task16/WP07 only, existing main, one implementation writer, no subagents/worktree, no scientific retuning. Previous source/freeze and all attempts remain intact. No protected outcome has been opened during implementation.

## Implementation and prospective rules

`runner.execute_frozen(digest_path, out, *, resume=False, dry_run=False)` verifies the full live protocol at each invocation before output/access admission. It uses the existing single global timed-run lock, cold `run_request`, authoritative complete-frame receipt times and immutable attempt publication. Each frozen deadline is a separate request. Queue order and shared-native fit semantics come directly from the verified queue.

Immutable paired-block generation records identify every planned physical attempt before launch. An external interrupt or incomplete generation allows a whole-block retry, preserving earlier attempts and cumulative per-request costs. The first wholly completed generation supplies effective outcomes; ordinary faults halt, retain last valid utility and flags, and are never silently retried. Correctness/resource/hash-drift stops persist as a halt artifact. The ordinary frozen fault rule is unchanged. All source changes require an A004 successor and current-source calibration before real execution.

The actual access journal is exactly `<outcome_directory>.access.json`, written durably before any existing outcome is read or a solver is launched. Each admission also gets an immutable event receipt. The frozen empty access ledger is never edited. Full strict protocol guard, per-worker live guard, recovery, release/publication and coordinator costs are visible. Per-worker guards check live source/environment/build, config/model/schema/queue/input pins; workers independently verify input/model identity. Full raw telemetry remains in immutable attempts; returned in-memory attempts use bounded resource summaries to avoid retaining thousands of large terminal payloads.

Operational metadata includes UTC/monotonic time blocks, load, available memory, free disk, coordinator RSS, power and process count when available. Temperature is explicitly unavailable; sandbox process enumeration returned PermissionError and is recorded as unavailable rather than fabricated. A public identity micro-measurement took 0.112229 seconds; this is an observation, not a timing guarantee.

## TDD evidence

- RED: `.venv/bin/python -m pytest tests/test_confirmatory_execution.py -q` — `10 failed in 3.94s`, each failing at `protected execute_frozen API is missing`.
- Sensor/admission RED: `.venv/bin/python -m pytest tests/test_confirmatory_execution.py -q -k 'unavailable_background or unfrozen_confirmatory'` — `2 failed, 10 deselected in 0.08s`: process telemetry raised PermissionError and an unresolved bare confirmatory worker was accepted.
- First GREEN: `.venv/bin/python -m pytest tests/test_confirmatory_execution.py -q -x` — `12 passed in 66.77s`. Includes real 252-request artificial cold-start fixture, all startup timeouts with zero utility; exact exhaustion and no-op resume. This is not the real protected cohort.
- CLI/persistent-stop RED: `.venv/bin/python -m pytest tests/test_confirmatory_execution.py -q -k 'cli_uses or live_source'` — `2 failed, 14 deselected in 1.31s`. Public-only CLI rejected confirmatory routing; live drift rejected the next launch but lacked a persistent halt record. CLI/config changes were removed before this RED, then reapplied after observing the failure.

## Milestone sequence

Completed: focused/full verification; code commit; A004/new experiment prospective public calibration and ancestry/access check; immutable successor freeze; real serial queue; final operational inventory. The sections below preserve the implementation and preparation history; the final execution section is authoritative for completion status. The root approved use of `configs/confirmatory-A004.json` because the illustrative original `configs/confirmatory.json` is a hash-bound historical A000 asset. No routing pointer or historical rewrite is introduced.

## Additional verification and self-review

- Focused GREEN: `.venv/bin/python -m pytest tests/test_confirmatory_execution.py tests/test_worker.py tests/test_harness_controls.py -q` — `99 passed in 101.29s`.
- Real native tiny fixture: `.venv/bin/python -m pytest tests/test_confirmatory_execution.py -q -k real_native` — `1 passed, 16 deselected in 8.79s`. One actual B0 request within the artificial frozen queue matched an independently exhaustively enumerated binary cover optimum; nonzero verified progress, frozen identity mapping and complete-receipt cutoff were checked. Remaining artificial requests used a bounded solver replacement while retaining real publication/recovery. No real protected sample was involved.
- Surviving-worker recovery RED: `.venv/bin/python -m pytest tests/test_confirmatory_execution.py -q -k partial_worker` — `1 failed, 17 deselected in 8.65s`, expected live-worker rejection was absent. GREEN after recording PID/create-time and checking liveness: `1 passed, 17 deselected in 2.41s`.
- First full suite: `.venv/bin/python -m pytest -q` — `718 passed, 1 warning in 143.98s`. Historical warning: joblib/loky could not discover physical-core count (`invalid literal for int() with base 10: ''`) and used logical cores. This was a discovery warning, not suppressed or represented as verified physical-core telemetry.
- Coordinator-cost RED: `.venv/bin/python -m pytest tests/test_confirmatory_execution.py -q -k coordinator_interruption` — `1 failed, 17 deselected in 2.99s`; interrupted batch lacked `start.json`. The correction durably records batch entry/admission and per-call coordinator CPU/elapsed lower bounds. An absent final accounting receipt explicitly leaves its tail unknown.

Self-review retained the existing runner organization (now about 1163 lines) rather than introducing an unplanned module split. Its size remains a maintainability concern. No architecture or scientific policy is silently replaced. An incomplete attempt with no independently established worker release stops conservatively; absent/reused recorded PID may establish release while its actual exit time and missing CPU/provenance remain unknown. No raw attempt is rewritten by recovery.

## Fixture identity collision — launch preparation paused for controller ruling

After final source verification, a metadata-only self-audit found that the inherited `tests/test_freeze.py::scientific` fixture copied the registered population master seed. Its generated 12-original confirmatory cohort therefore overlapped 12 identities in the 60-original real protected cohort. This was a fixture-isolation error. I reported it to the controller before any source commit, real public recalibration, A004 freeze, or real protected queue execution.

The real cold fixture used budgets **1, 4, 16 nanoseconds**. Every worker returned startup timeout, with no input-load timestamp, input-byte measurement, instance provenance, or progress packet. The worker checks startup deadline before `load_instance`; method validation may create an empty native model but never supplies the protected instance. All other overlapping fixture solver calls were artificial replacements producing manufactured values, not solver observations. The one real native tiny fixture uses 4/8 columns and 2/4 rows and therefore does not share the real 64/256-column original identities.

Evidence copied out of pytest's rotating temporary namespace is at `artifacts/task16/fixture-collision-evidence`; per-attempt hashes and packet/resource audit are `artifacts/task16/fixture-collision-audit.json`. The preserved 252-request run has 252 startup timeouts, zero progress bytes and only `pong`/`terminal` packets. It is evidence of a pre-input startup probe, not protected scientific solver output. This was referred to the controller; Ruling10 below replaced those 12 identities conservatively before execution.

A disjointness regression failed as expected (`1 failed, 18 deselected in 0.58s`) on instance-identity overlap. The shared scientific fixture now uses explicit master seed `artificial-freeze-tests-disjoint-v1`; the regression checks both instance and template identity disjointness against the registered protected manifest. This changes only tests, not the study population, generator, models, methods or deadlines. At that point verification of both affected test modules was pending and launch preparation remained paused. The subsequent GREEN and Ruling10 below resolved both conditions.

The declared-environment full suite before this test-only correction passed `718 passed in 143.11s`, with no warning. Its command was `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=1 .venv/bin/python -m pytest -q`. The earlier full run after coordinator-cost checkpoints passed `718 passed, 1 warning in 143.64s`; its warning transcript remains at `/tmp/task16-final-suite.txt`.

Controller Ruling10 resolves freshness conservatively: replace the 12 exposed/colliding identities (original indices 0–11), preserve the other 48 originals, and append fresh stable indices 60–71 under the unchanged generator/master/cell distribution. The selected successor remains N60, ten per cell, two repeats, one fit, 2520 logical requests. No solution or timing value selects replacements. All old inputs and registries stay intact; the successor receives its own selected manifest/registry and an identity-only exposure audit. The controller explicitly authorized resuming prospective preparation on this basis.

Post-isolation GREEN: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=1 .venv/bin/python -m pytest tests/test_confirmatory_execution.py tests/test_freeze.py -q` — **78 passed in 106.04s**, clean. This covers both changed test modules; runtime source was unchanged after the clean 718-test full suite. No further full repeat was needed. Compact verification transcripts and initial implementation inventory are in `docs/superpowers/evidence/task16/`.

## Source milestone and prospective preparation

Committed runtime/test milestone: `5acc206a8482710578f21ee90bb80ecd8a092828` (`feat: execute fixed serial protected comparisons`). Runtime source remains frozen at this commit during current-source public calibration and eventual protected execution; later evidence-only commits are separate.

The first static helper preparation under `artifacts/task16/source-calibration` stopped when the sandbox denied `sysctl -n machdep.cpu.brand_string`. It had written public inputs/configuration but launched no worker; these artifacts remain. A narrowly authorized hardware/preparation invocation succeeded in the separate `artifacts/task16/source-calibration-v2` namespace. No sensor value was fabricated.

Ruling10 inputs are now at `data/confirmatory/ra-wp07-e005/inputs/manifest.json`, with a new ownership registry. A preserved generated pool of 72 originals proves every old index0–59 retained identical input/template/cell/content hashes; selected indices12–71 retain48 and add12. All six cells contain ten originals and all selected weights are1/60. The public12-original manifest exactly matches the prior source calibration's original/template/content identities.

The metadata-only freshness audit checked **10,380 request metadata files** (including preserved/local test artifacts; this is not a distinct physical-attempt count) and **126 fixture manifests**, with no unresolved fixture entries. The new60 share no observed instance or template identity with any enumerated prior request/fixture. Exact sets and references are in `artifacts/task16/source-calibration-v2/freshness-audit.json`. The original60 and all previous registries/freezes remain unchanged.

`execution-prospective.json` fixes504 public and2520 protected requests, an explicit additional630s guard allowance (0.25s/request, grounded in the observed0.112229s cold guard call), minimum1GiB free storage and4GiB available memory, persistent resource/hash/correctness stops, whole-block external-interruption retries and no inference-driven decisions. Actual guard/coordinator costs will be reported; the allowance is not a guarantee. The fixed public calibration was the next timed step. No tests, fitting, or source/report edits overlapped it.

## A004 sealed before protected access

Fixed public source calibration completed504/504 on5acc206:344 complete,160 deadline; no faults. Repeat0 took309.264918084s and repeat1 took310.773780542s. The public calibration and registered four-seed numerical-stability check passed. No scientific field was tuned or selected from these measurements. `docs/superpowers/evidence/task16/source-calibration.json` records exact public cost sums and scope; overlapping wall/CPU scopes must not be added blindly.

- Runtime source hash: `a550040a87910fb4aa710ae9d33578dfd623a0b98b8fda0163dd3fb863557a05`.
- A004 digest: `72aba9929daa98bb48c64237ebba47e2c6d66e75d65165bf78a0355a53455457`.
- Queue SHA256: `6fa088859aeeac6bbd050c8e644cd029487ceaf66ca15d65bfbe5dd964d8bbff` (2520 requests).
- Config SHA256: `e13f31a7b098f372e12d653e46513d9f2d52fd587cb5841aff36ffbd8f36bffe`.
- Experiment/outcome namespace: `ra-wp07-e005`, `artifacts/runs/ra-wp07-e005`.
- Actual journal: `artifacts/runs/ra-wp07-e005.access.json`; absent before launch.

Full prospective resolution and sealing took2.801007417s wall/2.324670000s CPU. The actual CLI `run --config configs/confirmatory-A004.json --phase confirmatory --dry-run` returned0 and published no access/outcome. Strict dry-run plus explicit full ancestry audit took4.052680917s wall/3.291906000s CPU. All four ancestor namespaces/journals remain absent/empty. Detailed identities and guard costs are in `launch-verification.json`.

The current forecast with reserve plus prospective guard allowance is104.6538251475min. Storage envelope33,576,268,800bytes, worker RSS envelope1,217,331,200bytes, coordinator20GiB and OS4GiB give joint26,987,134,976bytes against38,654,705,664bytes physical memory; observed free storage at packaging81,087,307,776bytes. These are assumptions and operational limits, not guarantees. Both failed static preparations are disclosed: CPU-brand permission denial and a metadata audit that initially assumed template_id in minimal public manifests; the completed audit resolves IDs from input metadata and has no unresolved entry. Neither launched a solver; exact failed-preparation durations are unavailable.

The authorized command subsequently executed was `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=1 .venv/bin/python -m ra.cli run --config configs/confirmatory-A004.json --phase confirmatory --resume`. No edits/tests/fits overlapped that timed execution. Monitoring remained operational only, with no protected effects, significance, tuning or sample/order decisions.

## Completed A004 execution and operational audit

Status: **DONE WITH CONCERNS**, pending the controller's independent review. The concerns are measurement/provenance limits below, not an incomplete queue. The CLI exited 0 and its hash-validated status reports success. The immutable seal contains exactly **360 paired blocks, 2,520 logical requests and 2,520 physical attempts**: **1,640 complete and 880 deadline**. There were no startup timeouts, faults, quarantines, interruptions, repeated blocks, partial final manifests or unknown publication receipts. Every block uses generation 000000 and `first_fully_completed_generation`; no resume retry was needed. Historical attempts and costs remain untouched.

The single actual access event was durably recorded at **2026-10-14T09:02:00.477951Z**, before the first protected block. Final conditions were recorded at **2026-10-14T10:05:51.441672Z**. Source/models/features/configuration/environment remained unchanged throughout. Scientific scope remains 60 originals, ten per cell, two repeats, one genuine fit and six unique contrasts. Counts are 360 requests per physical method A/B0/B1/B2/B3/B5/B6, 1,260 per repeat and 840 per independent deadline 526707240/2106828958/8427315832ns. Registered fit mapping is 720 `shared` requests and 1,800 `task13-matched-fit1` requests; these are queue labels, not additional fitted models.

Execution seal: `artifacts/runs/ra-wp07-e005/execution-seal.json`, SHA256 **fa816d59deb649dafa1a00c5ecb59cb865bcd489a992963f956d986b809645c4**. Operational inventory: `docs/superpowers/evidence/task16/operational-artifacts.json`, SHA256 **7203c157ae40791fd8f21a656c167a9f08979e2d13eedb23495a5b138a348b02**. The inventory binds 3,608 operational JSON artifacts including the access journal, call receipts, generations/closures, progress and batch accounting. Attempt manifests/raw file hashes are transitively bound by the seal. No raw trace is staged.

The measured batch is **3,834.684718 seconds (63.91141197 minutes)**. Strict entry verification took 3.718029917s; the 2,520 live guards totaled 63.295173010s. Both are included in batch time/coordinator CPU, not hidden free overhead or additive costs on top of the batch. The initial cold identity observation 0.112229s informed the prospective 630s allowance; realized guard cost is an observation, not a promised bound.

| Operational quantity | Recorded total |
| --- | ---: |
| Request end-to-end wall before publication continuation | 3600.674989869s |
| Publication continuation | 88.880694529s |
| Request wall including publication | 3689.555684398s |
| Batch less request wall (guards, audits, other coordinator work) | 145.129033602s |
| Whole coordinator CPU | 514.584103000s |
| Request-scoped parent CPU, a subset of coordinator CPU | 377.562958000s |
| Worker CPU measured lower bound | 3347.089174268s |
| Deadline overshoot sum | 50.364064041s |
| Parent observation overlapping worker wall | 105.885548777s |
| Parent sampling | 2.740795883s |
| Initialization wall / CPU | 5.330012876s / 2.958449000s |
| Trace bytes | 2522350036 |
| Total protected output bytes at audit | 4591473863 |
| Maximum recorded worker RSS | 297369600bytes |

These scopes overlap as marked and must not be blindly summed. All 2,520 attempts have worker CPU/RSS fields, raw instance provenance, aligned clocks, confirmed release, complete timing partitions and publication accounting. Instrumentation failures, fallback counts, unknown worker CPU/RSS attempts, duration-censored attempts and unknown publication attempts are zero. Nonetheless every record explicitly says `cpu_tail_unmeasured=true`: pre-terminal-cleanup CPU does not observe every instruction through exit. Parent wait/release wall is retained. The final batch accounting write tail, report writes and interactive status-monitoring costs are not fully instrumented. Failed static preparation durations remain unknown as disclosed above. These sums are not an exact full-project cost.

Across 360 block-start snapshots, available memory ranged 10356850688–13839728640 bytes, coordinator RSS 119504896–561545216 bytes, and free disk 75364175872–81075146752 bytes. Final coordinator RSS was 480018432 bytes. One-minute load ranged 3.70458984375–8.80712890625 on the declared 14 logical CPUs. Every power snapshot reported AC and 100% charged. Temperature and process-count sensors were unavailable in all 360 snapshots, with exact reasons retained. No resource threshold, correctness alarm or source drift triggered. These boundary observations are not continuous resource maxima.

Post-run audit command:

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=1 .venv/bin/python /tmp/task16-operational-audit.py > /tmp/task16-operational-audit.log 2>&1
```

It exited 0 with `status=complete`, 2,520 logical/physical requests, 360 blocks, 1,640 complete/880 deadline and the zero-fault inventory above. It reran strict `verify_protocol`, matched each expected frozen Request to its raw manifest, checked 2,520 attempt-manifest hashes and **337,955 raw artifact hashes covering 2,573,455,496 bytes**, verified serial launch/release and coordinator-call intervals, matched raw provenance and one-thread fields, reconciled all closures/selections/progress/cost/status totals, and verified journal admission precedes the blocks. No utilities, effects or significance were summarized. Audit time was 104.118770833s wall/77.585235s CPU, including 3.800237208s strict verification, after primary timing. Final evidence write tail is excluded. The exact script/output are preserved as `docs/superpowers/evidence/task16/operational-audit-script.txt` and `operational-audit-output.txt`; machine inventory is `execution-audit.json`. No further test suite was repeated after accepted source checks because runtime source did not change.

## Commit and handoff inventory

- Runtime/test milestone: **5acc206a8482710578f21ee90bb80ecd8a092828**, `feat: execute fixed serial protected comparisons`.
- Prospective calibration/cohort/freeze: **36a67e0c063666293e79203e795a699a19aad03f**, `protocol: seal A004 source calibration and fresh protected cohort`.
- Execution evidence milestone: the commit containing this operational report and sealed metadata; its hash is recorded in the final task handoff.

The runtime pin remains 5acc206, distinct from evidence-only commits. Environment hash: **581c89be8c1343d6f925483e82100f4fe81293fea771eedb21aac08a296c5329**. Build hash: **090e514d7d7581d68bdd17d6880096b12008861c21e34fa31d3d2fa18803cbaf**. A004/digest/config/queue/source hashes appear above and in the machine evidence. Previous freezes/configs/registries and colliding fixture evidence remain preserved. A004 records exposure-based replacement of 12 originals; no performance-based selection occurred.

Remaining limitations: optional sensors and incomplete cost tails; one genuine policy fit, so later inference is conditional on frozen assets/training data; large raw artifacts remain local and must be retained for Task17; runner remains 1,163 lines and warrants maintainability review. The fixture identity collision was detected before real protected execution and resolved by controller Ruling10. No learned superiority or negative confirmatory result is claimed here. The controller owns independent review and separate Task17 historical analysis using frozen envelope/source identities; later analysis source must not be relabelled as this execution's runtime source.
