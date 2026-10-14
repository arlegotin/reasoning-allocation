# Final whole-branch review

Reviewed range: `562c574..6c083ca` (HEAD `6c083ca2439344e2e38e3d59b2cf4aa0d6b6d3a7`), 82 commits. Reviewer: `/root/final_whole_branch_review`. Scope: completed local reasoning-allocation PoC against the versioned specification, implementation plan, final-review handoff and binding global constraints. No helpers or subagents were used.

**Counts: 0 Critical, 1 Important, 2 Minor. Ready to merge/close: With fixes.** The Important finding is a prospective correctness-quarantine bug. Neither it nor the two Minor findings establishes an error in the preserved zero-fault A004 numerical results. Final archive closure remains explicitly controller-owned and pending.

## Strengths

- The runtime has meaningful ownership boundaries despite two large orchestration modules. Allocators receive primitive records; native wrappers are resolved in callback scope. Live ancestry, restart epochs, immutable comparator ordering, deduplicated completion work, and per-lease credit are handled separately. The ordinary controls and local/pooled treatments change allocation rather than pruning or solver correctness settings (`src/ra/scip_backend.py:93`, `src/ra/leases.py:13`, `src/ra/candidates.py:22`, `src/ra/config.py:151`). Installed-build lifecycle tests include real native behavior, not only mock restart counters.
- Cold availability is consistently defined by parent receipt. Worker-side integer verification, monotonic handshake checks, sequenced progress, exact deadline inclusion, immutable assignment identity, and independent saved-assignment reconstruction form a coherent chain (`src/ra/observer.py:61`, `src/ra/runner.py:224`, `src/ra/metrics.py:27`, `src/ra/report.py:33`). Late messages cannot improve the reported deadline endpoint. Worker and parent timing scopes, overshoot, lower bounds and unknown tails are distinguished rather than added indiscriminately.
- Local features have a strict ordered whitelist and explicit masks; the 192-column local input and 109-column pooled addition remain distinct. No teacher optimum, future lease outcome or future parent receipt becomes a runtime input. Randomized collection logs actual pool/action support and propensity. Training preserves zero gains, filters duration lower bounds, gives originals equal aggregate target weight and retains historical eligibility corrections (`src/ra/features.py:16`, `src/ra/collect.py:72`, `src/ra/train.py:21`, `src/ra/models.py:153`). Cached-prediction repricing after material trace work addresses the historical dispatch-timing issue.
- Native tuning and the attribution controls are substantive. The Task13 drivers include actual native selector/plunging alternatives, separate fixed-length data/fits, capacity comparisons, pooled context, all-frontier diagnostics, and the later bounded actual-regime tuning wave. Their finite resource/stopping and screening limits are explicit; they are not presented as proof of global saturation (`checks/task13_controls.py:85`, `checks/task13_tuning.py:46`). B4's selected L1 alias does not create another fit, request or contrast.
- Freeze and execution checks bind configurations, source/build/environment, model/schema assets, original input identities, queue, exclusion policy and resource envelope. Successor checks walk prior access/identity ancestry. The current prospective storage guard includes per-attempt and final metadata, while preserving the originally executed source (`src/ra/freeze.py:106`, `src/ra/freeze.py:222`, `src/ra/runner.py:962`). Protected execution is fixed and serial, and ordinary faults halt diagnosis rather than silently replacing a method.
- Statistical code preserves paired budgets/methods/repeats within original-template clusters and shares native observations across the fit axis. Fit resampling is globally crossed. The report correctly conditions on the single genuine fit, retains all six simultaneous contrasts, and does not promote B6's unstable Monte Carlo diagnostic, narrow B3/B5 intervals, or a selected public result into a stronger claim (`src/ra/stats.py:141`, `REPORT.md:5`, `CLAIMS.md:15`).
- The final report keeps methodological implementation, measured improvement and deployment value separate. It reports no positive superiority, conditional negative A–B2, other directional uncertainty, near-ceiling population limits, blocked named contenders and unexecuted studies. The added reuse tables authenticate a specific fitting component and explicitly leave complete extra preparation cost unavailable; they do not invent a speedup or warm-service forecast (`src/ra/report.py:565`, `src/ra/report.py:678`). The qualified PNG was visually inspected: all six contrasts, one-fit title, ordinary/simultaneous distinction and B6 instability footnote are readable.
- Reproduction and archival design are unusually explicit. Original solver `5acc206`, original analysis `42a0b88`, interpretation correction `df9df35`, clean reproduction `59690b7` and current code remain different source generations. The clean driver writes separate results, uses the same frozen seed/draw count, checks exact numeric digest/five CSV byte sequences, and separately checks native binary/parameter parity and one public native request. Archive receipts sit outside their copied trees; large raw/model/wheel assets and failures remain retained, with original absolute-path restoration documented.

## Issues

### Critical (Must Fix)

None found.

### Important (Should Fix)

**I1 — A later parent failure can erase an already observed correctness alarm and disable configuration quarantine.**

- Locations: `src/ra/runner.py:338`, `src/ra/runner.py:362`, `src/ra/runner.py:414`; downstream `src/ra/runner.py:614` and `src/ra/metrics.py:131`.
- A worker terminal `numerical_alarm` initially sets `status`, but parent failure/interruption/signal handling and, particularly, the `finalize_trace` exception handler can replace it with an ordinary status. The final `Attempt.quarantined` is then computed only from `status == 'numerical_alarm'`. The earlier terminal alarm remains in `resources.worker_terminal_status`, but resume and endpoint consumers do not use it as quarantine evidence. The final checkpoint also replaces the earlier checkpoint that had correctly recorded quarantine.
- Concrete focused probe: a synthetic socket worker performed the real clock handshake, sent a `numerical_alarm` terminal with `error='injected correctness alarm'`, and exited without importing SCIP or loading an instance. Monkeypatching only the parent `finalize_trace` to raise `ValueError('injected trace finalization failure')` produced:

```json
{"terminal_status":"numerical_alarm","status":"implementation_error","quarantined":false,"error":"collection finalization: injected trace finalization failure"}
```

  `resume_requests([request], temporary_root)` returned zero pending requests without raising configuration quarantine. Thus an observed correctness alarm becomes an ordinary completed fault to recovery. The protected runner still halts on an implementation error, which limits immediate damage, but the required persistent quarantine contract and downstream scientific classification are lost.
- Preserve correctness-alarm state independently and monotonically through subsequent failures. Keep the original alarm provenance and secondary errors; ensure final/partial attempts, trace eligibility, resume and analysis consumers cannot downgrade it. Add focused compound-fault regression coverage, including a terminal alarm followed by trace-finalization failure and a later transport/interruption error. This needs no solver experiment or reanalysis of A004. The recorded A004 cohort had no faults, so this finding is not evidence that its existing results need replacement.

### Minor (Nice to Have)

**M1 — The public tuning-summary helper accepts general budget grids but uses incorrect frontier weights for them.**

- Location: `checks/pilot_tuning_summary.py:37`.
- The new explicit-budget and cohort guards are useful, but the helper still hardcodes `[.25,.5,.25]` for any three budgets and uniform weights otherwise. The specification's frontier is normalized trapezoidal integration on log deadlines. Unequally spaced triples and grids of four or more points can therefore produce the wrong public ranking.
- A pure in-memory probe using the complete grid `[1,4,16,64]`, A utilities `[1,0,0,1]`, and B utilities `[0,.7,.7,0]` returned weights `[.25,.25,.25,.25]` and ranking A before B. `ra.metrics.log_budget_weights` gives approximately `[1/6,1/3,1/3,1/6]`, with A=1/3 and B=0.4666667, reversing that ranking.
- Use the shared log-weight function for multi-deadline grids, retaining a documented weight of one if a single-deadline screening summary is supported, or reject unsupported grids explicitly. Add a compact hand-calculated ranking regression. Current A004 inference uses the correct independent weight path; the historical near-equally-log-spaced Task9 grid is not shown to have changed selection by this probe.

**M2 — The implemented `check` command lacks the promised dry-run interface.**

- Locations: `src/ra/cli.py:19`, `src/ra/cli.py:115`; requirement: specification §11, “Every command has … dry-run support.”
- `check --suite analytical --out PATH --dry-run` is rejected by argparse; the only route always executes diagnostics and writes its report. Other implemented primary commands expose the flag, so users cannot apply the common preview workflow to this command.
- Add a no-write dry-run that validates the selected implemented suite and describes its output/operations. A small CLI assertion can ensure it leaves the output path absent. This is a low-impact command-contract gap, not a scientific-result defect. The gated, unimplemented transfer command is a different and justified scope disposition.

## Plan alignment and scientific gates

The achieved package is a completed negative/inconclusive confirmation plus a narrow public latency diagnostic, not an implementation of every envisioned extension. This is allowed by specification §1 and WP10's achieved-scope contract. I independently checked the gate reasoning rather than treating earlier approvals as sufficient.

- WP00–WP07: source, interfaces and saved evidence support the implemented environment/native checks, analytical/exactness work, cold harness, public headroom/tuning, local/pooled controls, freeze, fixed execution and paired analysis. I1 is an outstanding exception to the failure/quarantine contract; M2 is a smaller CLI contract exception.
- Contemporary contenders: source/access cards and register require separate author-code/checkpoint/teacher/dependency permissions and actual fidelity/resource evidence before execution or named superiority. All five are explicitly blocked and all associated execution gates are unrun. This is an allowed narrower comparison set, not proof of infeasibility or defeat. No permission was inferred from dependency licenses.
- WP08: the selected latency diagnostic is prospective, finite, public and explicitly descriptive. Existing public support motivated doses and deadline; case membership was index-based. Population engineering requires a concrete representation-specific question, which generic administration burden does not supply. The plan explicitly calls for the smallest selected discriminating treatment; it does not require an exhaustive robustness grid after this negative/inconclusive outcome. Wider robustness and independent-fit/shift/warm treatments remain unexecuted, with no claims based on them.
- WP09: the documented entry predicate requires meaningful primary benefit with attribution or a specific evidence-supported locality/scale prediction. Neither is established. Skipping all four tracks before source/license/storage feasibility assessment is justified; those feasibility questions remain unassessed.
- WP10: saved validation establishes the required clean fixed reproduction within achieved scope. Reporting/reuse/claim boundaries are present. Current status prose intentionally says review/archive closure is pending; that is accurate at this review and must be updated by the controller only after the fix wave, scoped rereview and final archive verification.

## Required deferred-observation triage

| Earlier observation | Independent final disposition |
|---|---|
| Task2 capability diagnostics mixed with production adapter | Still visible: production adapter/plugins occupy the first portion of `src/ra/scip_backend.py`; capability fixtures and report discovery start at line621. Accept as nonblocking maintenance debt. Move diagnostics behind the same public interface in a future source generation if the module is extended; no broad refactor is required to validate the completed experiment. |
| Task16 large protected orchestration function | Still visible in `src/ra/runner.py:993`: history/recovery, admission, launch, accounting and sealing share one function. Accept the disclosed nonblocking deferral; future extraction of history/recovery and resource/seal units would improve auditability. I1 is a separate concrete defect in request failure handling, not a demand to refactor this function. |
| Task5 Boolean probe ratio | Addressed: `src/ra/config.py` explicitly rejects Boolean/nonfinite ratio entries. Do not reopen the old finding. |
| Task6 duplicate incumbent verification | Addressed: `Observer.poll` verifies a new assignment once and commits the checked object. An unchanged verified cost reuses the existing valid deliverable. |
| Task6 inventory-cache warning / Task18 environmental warning | Historical warnings remain disclosed; later clean validation is recorded. No current source defect identified from those environmental observations. |
| Task8 nonstandard native Infinity JSON | Addressed in installed-parameter metadata: unbounded endpoints become null, and strict JSON readers reject nonfinite JSON constants. |
| Task9 phase label and incomplete/duplicate budget guards | Original findings addressed: helper preserves its single public phase and requires explicit unique complete grids and matched method cohorts. M1 above is a distinct remaining weight-calculation issue exposed by a newly supported general grid. |
| Task12 selected-deployment documentation | Addressed in the final report: `selected_deployment` belongs to the training summary; compact model-card deployment is under `selected.allocator` / `selected.learned`. |
| Task14 register ID type validation | Addressed before set construction (`src/ra/baselines/register.py:185` and following supplied-card check). |
| Task15 bootstrap counts1–3 | Addressed in planning and final inference validation (`src/ra/stats.py:30`, `src/ra/stats.py:154`). |
| Task17 standalone B6 annotation and fixed A004 renderer boundary | Addressed: inspected readable qualified image, explicit numeric/config/audit/curve validation, and separate presentation destination. |
| Task20 missing separate reuse deliverable | Addressed: independently read selected-asset matching and historical-inventory membership in the builder, cost/utility tables and preserved limits. Saved scoped rereview records exact arithmetic verification and29 passing covering tests. |

These accepted maintenance deferrals are explicitly triaged, not silently dropped or counted as additional new findings.

## Verification performed and boundaries

The supplied review package is 11,243,464 bytes, 694 changed files, including28 source files,36 test files,23 check drivers and large repetitive artifact/config/evidence sections. I reviewed it in sections using current source, targeted historical diffs, specification/plan text, tests, compact evidence cards, report inputs and structured inventory summaries. I traced core integration directly and inspected the delta from original solver `5acc206` to reviewed HEAD: subsequent changes include reporting/inference, prospective storage accounting, and public latency instrumentation, rather than silently treating current source as the executed solver. Repetitive per-block receipts, checksum lists and endpoint tables were assessed through their schemas, authentication/reconstruction code and retained summary evidence; this is not a new exhaustive physical hash audit of every ignored descendant.

Saved verification read during this review includes the pristine clean-environment transcript **788 passed in161.05s**, the separate **84 native checks**, Task20 scoped **29 passed in1.06s**, offline hash-locked installation/parity and exact numerical reproduction receipts. The latter records2,520 reconstructed endpoints, numerical digest `6339521bccab940fe0ec0546792a3c6012e65644fe7f63a5dde6418717b83d69`, five exact CSV matches and tolerance zero. These are saved executed evidence, not tests or scientific work rerun by this reviewer. The documented erroneous clean-suite invocation and subsequent correction remain visible.

Two new named focused probes were necessary:

1. **Sticky correctness quarantine after secondary failure:** actual parent transport/finalization/recovery path with a synthetic standard-library worker, no instance loading or SCIP execution; temporary files only. It confirmed I1.
2. **Declared-grid frontier weighting:** pure in-memory public synthetic rows, no filesystem writes or statistical resampling. It confirmed M1.

Both ran with bytecode writes disabled. No inference/bootstrap, fitting, solver solve, full/focused test suite, dependency install, protected reconstruction, clean reproduction, protected asset rewrite, source/index/HEAD change, branch/worktree operation or helper-agent dispatch was performed. The only retained review write is this requested report. Final `git status --short` was empty and HEAD remained `6c083ca2439344e2e38e3d59b2cf4aa0d6b6d3a7`. The original numerical result is assessed through source and saved authenticated evidence; absence of undeclared off-protocol activity, unknown CPU exit/setup tails and universal native correctness cannot be independently proved by this review.

Final physical archive closure is not yet verified because the controller must first add this review, the single fix wave, scoped rereview, rulings and final receipts. Existing pre-final retention and restore instructions are coherent; no scratch deletion is justified before their final documented refresh and verification.

## Recommendations

Make one consolidated fix wave for I1 and the two small command/helper gaps, with focused synthetic regressions. Preserve all original scientific sources, data, inference, plots and reproduction receipts; label the fixes as a future source generation. Then perform the scoped rereview and controller archival closure. Do not reopen protected experiments, add inferential draws, or spend a broad refactoring/test cycle to reconfirm unchanged evidence.

## Declined to judge

- Performance or generalization on populations, independent training fits, shifts, warm persistent services or transfer domains that were not executed: outside the achieved experiments; no such claims are accepted.
- Native population-versus-queue performance and independent solver-replica behavior: the engineering gate was unmet; analytical coupling is judged only as an invariant.
- Fidelity or performance of unimplemented contemporary ports, and present-day remote access/reuse permission beyond the pinned audit: no executable port or current permission claim exists; the register's blocked disposition is assessed instead.
- Universal correctness across untested SCIP versions/ABIs or operating systems, and hard-real-time guarantees: the contract and evidence are installed-build/local and explicitly permit native overshoot.
- A production distribution/relocation mechanism beyond the documented original-path restoration, and multi-user security for arbitrary untrusted model pickles/configurations: this is a local trusted-asset research PoC; the retained locks/hashes/path checks and restoration contract were reviewed.
- Proof that no undeclared human/off-protocol outcome access or unmeasured machine work ever occurred: saved journal/provenance evidence bounds the claim, but cannot establish a universal absence assertion.
- Final archive completeness after the not-yet-performed controller closure: explicitly a subsequent required action; this review accepts no completion claim for it.

## Assessment

**Ready to merge/close? With fixes.**

The branch implements a coherent, measured and conservatively reported local experiment, with substantial real integration testing and exact saved-result reproduction. Preserve that result; fix the independently confirmed quarantine downgrade before final acceptance, address or explicitly rule on the two Minor gaps, then close the archive through the prescribed controller process.
