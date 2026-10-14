# Consolidated final fix wave

Base: `6c083ca2439344e2e38e3d59b2cf4aa0d6b6d3a7`, current `main`, one writer, no subagents, branch/worktree operations, push, merge or deployment. Requirements: `final-fix-brief.md`, original `final-whole-branch-review.md` I1/M1/M2, `global-constraints.md`, and current REPORT/REPRODUCE source/immutability contract.

## Changes

- **I1:** `runner._run_request` records the observed worker correctness alarm independently of later status handling, including its source, authoritative receipt time and original error. Interim checkpoints and final attempts retain quarantine. Alarm status wins before trace finalization and after a finalization fault; original and subsequent error details are concatenated. Parent interruption remains duration-censored even when correctness status takes precedence. Existing resume/configuration quarantine and endpoint/scientific consumers continue to receive the canonical alarm status/flag. There is no broad orchestration refactor or historical attempt migration.
- **M1:** the public tuning helper calls `ra.metrics.log_budget_weights` for every multi-budget grid. A single-budget screening score has explicit weight one. No historical tuning summary, selection or scientific inference is regenerated.
- **M2:** `check --suite analytical --out PATH --dry-run` validates the supported suite through the real CLI parser and returns its four operations and `PATH/design.json` destination without running diagnostics or creating PATH. Unsupported suites still fail clearly.

## Regression evidence

New compound-fault tests replace only the launched worker with a standard-library socket script, using the real clock handshake, parent receipt stream, valid available assignment, trace finalizer, publication, recovery and endpoint summarizer. Temporary tiny input/trace fixtures are isolated from scientific data; the worker imports no SCIP and performs no solve. Cases cover alarm/ordinary terminal outcomes crossed with trace-finalization failure, later malformed transport, parent interruption, worker SIGTERM, and interrupted final publication. Assertions cover persistent partial/final quarantine, original alarm provenance and secondary errors, available utility 0.5, closed trace-label eligibility, config quarantine across request IDs and endpoint correctness flags. The ordinary controls retain utility without acquiring an alarm.

The weighting regressions have independently hand-calculated expectations: unequal log triple `[1,2,16]` has weights `[1/8,1/2,3/8]`, scores A=1/8 and B=3/16; four budgets `[1,4,16,64]` have weights `[1/6,1/3,1/3,1/6]`, scores A=1/3 and B=7/15. Both rank B above A, unlike the old helper. The single-point case retains weight1. CLI checks call the actual parser/dispatch, fail if diagnostics execute, inspect preview fields and ensure the output path remains absent; unsupported-suite coverage also launches the module as a subprocess.

All pytest invocations use the retained clean interpreter with absolute source path and all three thread caps:

```sh
PYTHONPATH="$PWD/src" OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=1 \
  artifacts/task20/clean-reproduction/env/bin/python -m pytest -q ...
```

1. RED arguments: `tests/test_compound_faults.py tests/test_pilot_gates.py::test_tuning_ranking_integrates_declared_log_grid tests/test_design_checks.py::test_analytical_cli_dry_run_describes_without_diagnostics_or_writes tests/test_design_checks.py::test_check_cli_dry_run_rejects_unsupported_suite`. **8 failed, 7 passed in1.02s**, exit1. Failures: the five alarm compound-fault cases (four lose scientific classification; publication preserves quarantine but lacks original alarm checkpoint provenance), unequal triple/four-grid weights, and argparse rejection of dry-run. Ordinary controls, single screening, and unsupported suite already pass. Complete transcript: `docs/superpowers/evidence/final-fix/red.txt`.
2. Same arguments after the first implementation: **15 passed in0.74s**, exit0; `green.txt`.
3. Self-review added a censor assertion to the existing compound test: `tests/test_compound_faults.py`, **1 failed, 9 passed in0.67s**, exit1; `censor-review.txt`. The failing case is `test_observed_alarm_survives_secondary_parent_failure[interrupt-numerical_alarm]`: worker release before parent interruption left the censor flag false once alarm status won. The subsequent change preserves that flag independently. This unsuccessful verification is retained, not hidden.

4. Covering arguments: `tests/test_compound_faults.py tests/test_worker.py tests/test_deadlines.py tests/test_recovery.py tests/test_collection.py tests/test_lease_labels.py tests/test_metrics.py tests/test_harness_controls.py tests/test_confirmatory_execution.py tests/test_report.py tests/test_design_checks.py tests/test_pilot_gates.py`. **300 passed in124.06s**, exit0; `scoped.txt`.
5. A final trace-censor assertion initially passed with the nondeterministic worker exit timing: `tests/test_compound_faults.py`, **10 passed in0.65s**, exit0; `trace-censor-review.txt`. The fixture was tightened to wait for the synthetic worker's completed exit before injecting parent interruption. This exposed the precise remaining boundary: the censor flag was normalized after trace finalization, so trace metadata could disagree with the final attempt. **2 failed, 8 passed in0.70s**, exit1; `trace-censor-red.txt`, failures `[interrupt-numerical_alarm]` and `[interrupt-complete]`. Moved the existing censor normalization before trace finalization; no additional fault taxonomy or research change.
6. Final scoped arguments: `tests/test_compound_faults.py tests/test_lease_labels.py tests/test_metrics.py tests/test_design_checks.py tests/test_pilot_gates.py`. **74 passed in2.53s**, exit0; `scoped-censor-green.txt`.

7. The single full clean-suite invocation ran with the same environment, `/usr/bin/time -p artifacts/task20/clean-reproduction/env/bin/python -m pytest -q`, on committed source `4bd1fa411b623bb10b451a6d94fb314947694b93`: **804 passed in149.62s**, exit0, no failures/warnings; `full-clean.txt`. Outer time: real149.83s/user103.18s/system38.00s, overlapping the pytest scope. No second full suite was run. Final code/test paths remain byte-identical to that source commit.

`docs/superpowers/evidence/final-fix/validation.json` records exact argv, environment, exit codes, all eight test invocations and transcript SHA256s. One optional read-only `ps -axo pid,ppid,etime,pcpu,command | rg 'pytest|ra.worker|synthetic_worker'` progress diagnostic returned `operation not permitted: ps` (exit1); it was not retried or escalated, and did not interrupt pytest.

Initial `git add` was sandbox-denied because `.git/index.lock` was read-only; the authorized escalated staging succeeded. The first manifest refresh consequently lacked the not-yet-staged new files and was rerun after staging using the exact REPRODUCE recipe. The subsequent cached diffcheck found trailing whitespace generated by pytest in three RED transcripts. The already-queued commit proceeded despite that failed check; this packaging sequencing mistake is retained here. Commit `4bd1fa4` preserves the original raw transcript bytes; `packaging-check.json` retains an exact unredacted read-only replay of that whitespace failure against the immutable commit. Final evidence copies remove trailing whitespace only, preserving all results/failing names; final manifest/diffcheck verification is repeated after staging the completed evidence. No test or scientific source was altered to correct transcript formatting.

## Preservation and source generations

Read-only hash verification against base MANIFEST checked **687 unchanged original tracked files**, excluding the six intentionally mutable source/test/document paths. It also verified **all54 path/SHA references** recursively present in the retained clean-reproduction receipt. `docs/superpowers/evidence/final-fix/preservation.json` records exact references and scope. This is not a new exhaustive physical audit of every ignored raw descendant. No command in this wave writes original data, config, model, inference, image, artifact index, freeze, source snapshot or clean-reproduction results. Tests use temporary fixtures; the retained environment is reused without installation.

Both preservation checks were repeated after the final suite and passed unchanged. REPRODUCE now names the prospective source and test evidence while leaving final review/archive acceptance controller-owned.

Original solver source `5acc206a8482710578f21ee90bb80ecd8a092828`, original analysis `42a0b88b08d6158629aa77d371d32cb6e433c4ad`, interpretation-only correction `df9df35403883458af9eee103093e820a7f3de71`, and clean reproduction `59690b751bbecbe135560aa57e8c7ffe6d4a9912` remain immutable and distinct. Original numerical digest `6339521bccab940fe0ec0546792a3c6012e65644fe7f63a5dde6418717b83d69` and inference bytes are retained. This fix is prospective future execution source, never the executed A004 source. No new solver study, fit, inference/bootstrap study, protected cohort, reconstruction or scientific reproduction was run. Existing isolated native/statistical test fixtures remain verification, not new research evidence.

## Self-review, costs and limits

The final production delta is confined to three reviewed paths. Existing consumers use the preserved status/quarantine fields, so no recovery/statistical policy migration is necessary. The shared frontier function already validates its multi-point input; the public helper retains explicit unique positive complete matched grids. Check execution still uses its original implementation outside dry-run. No broad helper/refactor or unrelated deferred-maintenance work is included.

Pytest-reported wall times are verification costs, separate from scientific expenses. Development, diagnosis, process startup, monitoring, hash checks, receipt writing and unknown CPU/exit tails are not zero and are not inferred from the pytest times. No additional scientific work is costed as zero merely because it was not repeated. Final whole-suite timing is recorded independently when available; overlapping scopes are not added into a project total.

Controller-owned scoped rereview, rulings, review acceptance and final archive/documentary closure remain pending. This report does not mark WP10/archive closure complete or authorize scratch deletion.

## Commits

- `4bd1fa4`: consolidated prospective implementation, regressions, initial verification/preservation evidence and refreshed manifest. All final suite source/test code is committed here. Later evidence publication is documentary only.
- `2d4c619b85ed5ed377b249a51b6d4f6e516d81c4`: final verification receipt/transcript, post-suite preservation checks, prospective-source REPRODUCE note, whitespace-only readable transcript copies and refreshed manifest. **Final HEAD**.

Final publication gate, executed sequentially before the evidence commit: all **705** entries passed `shasum -a 256 -c MANIFEST.sha256` (exit0; local check transcript `/tmp/ra-final-fix-manifest-final.txt`), `git diff --check` and `git diff --cached --check` passed (exit0), and `git diff --exit-code 4bd1fa411b623bb10b451a6d94fb314947694b93 -- src tests checks` passed (exit0). The commit ran only after inspecting those successful exits. Final `git status --short` is empty. No further source changes or test reruns followed the successful full suite.

**DONE** for the single authorized I1/M1/M2 fix wave. No unresolved implementation finding was found in self-review. The documented failed intermediate checks, packaging sequencing mistake, unmeasured cost tails and non-exhaustive ignored-tree preservation audit remain visible limits. Root still owns the one scoped rereview and final archival/documentary acceptance; this is not overall branch closure.
