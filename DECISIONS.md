# Decisions

All entries below are dated 13 October 2026. D001–D007 concern the documentation deliverable; execution evidence starts at D008.

## D001 — Preserve branch and planning scope

The user requested a Superpowers spec and plan, work on the current branch, and meaningful commits. Initial inspection found an empty checkout on `main` with no project instructions. Write repository documents and make separate specification, plan, and handoff commits on `main`. Dependency installation, product scaffolding, solver experiments, and implementation remain future work.

## D002 — Treat the detailed brief as the design input

The supplied brief already fixes the domain, queue-first approach, allocation/evidence boundary, baselines, cold timing, and risk order. No additional preference question was needed to write these documents. Hardware-dependent and scientific calibration values belong to named capability/pilot gates rather than invented constants. Scope and methodology changes during execution use numbered amendments.

## D003 — Make the repository handoff self-contained

The Superpowers builder check identified a dependency on an unavailable external brief and insufficient procedure for Appendix A. The final spec is complete implementation authority; omitted research narrative creates no hidden requirement. Preserve the complete supplied standard-library diagnostic inside the spec for faithful future reproduction. Keep reported preparation evidence distinct from measurements performed in this checkout.

## D004 — Use separate local and available progress channels

Worker features may consume progress already validated locally. Parent receipt time defines deadline availability, training endpoint gains, and evaluation. Reconstruct labels offline from recorded receipt times and aligned decision boundaries; future receipts cannot become runtime features. Record raw body duration separately from administration and total predicted decision cost.

## D005 — Fix small engineering conventions explicitly

Use focused Python modules, immutable primitive node records, original integer feasibility checks, canonical configuration/asset hashes, atomic per-attempt manifests, and complete-request recovery. Clone count is `floor(clone_fraction*n)`; bridge multiplication precedes clone perturbation. Backend progress tuple order is primal, dual, local utility. None of these choices changes the solver's transition rules.

## D006 — Preserve strong comparison and valid stopping paths

Keep B0–B6 core controls, serious native tuning, horizon attribution, pooled/global context, and source/permission/parity gates for B7–B9. Missing competitors narrow the claim. Population representation must first match queue trajectories; transfer has its own evidence/license/resource gates. Early low-headroom, correctness, capability, negative, or inconclusive outcomes are reported within their achieved scope.

## D007 — Limit this session's source verification

Opened official PySCIPOpt node-selector/event-handler documentation, PySCIPOpt 6.3.0 release metadata, and scikit-learn histogram-gradient-boosting documentation to check the proposed stack/interface path. No dependency was installed, and no wheel metadata was treated as proof of local compatibility. The broader literature assessment remains attributed to the supplied brief, with exact-source reproduction gates retained in the plan.

## D008 — Resolve the environment on the actual target

The target reports Apple M3 Max, native ARM64 Python 3.12.9, 36 GiB memory, 14 logical CPUs, macOS 26.7.1, Rosetta translation 0, AC power, and power mode 0. PySCIPOpt 6.3.0 binary wheels link SCIP 10.0.2 / SoPlex 8.0.2. No source build, system Python replacement, machine setting change, remote compute, or PyTorch dependency was needed. Network installation and read-only sandbox-blocked hardware commands used the task's authorized escalation. Retain raw discovery privately and version only compact summaries plus the exact macOS ARM64 artifact-hash lock.

## D009 — Distinguish the smoke check from native capabilities and timings

The doctor solves and independently checks the original tiny cover at objective 2 with solver and LP thread limits set to one. It records versions, full parameter values, numerical-library configuration, resource snapshots, and diagnostic import/solve/discovery durations. This is an environment check, not an allocation benchmark or proof that lifecycle/restart callbacks satisfy WP00. The initial installation's full wall duration was not instrumented; retain that limitation instead of estimating it. A timed offline locked-wheel reinstall is recorded separately as setup cost. Target capability checks and scientific gates remain pending.

## D010 — Installed API and native lifecycle determine capability

The installed PySCIPOpt source exposes `getNRuns()`, despite its absence from the online Model API page examined earlier. Real native diagnostics establish run 1→2, root-number reuse, and explicit main-tree scope. A temporary presolve root can share the later main root's number; it is excluded from main-tree identity/credits while its time remains charged. No native bridge or NodeKey contract amendment was needed.

## D011 — Preserve native counter differences

A propagation-only terminal root has one native node and zero completion-mask events. Selected no-LP descendants in a separate diagnostic emit completion events and reconcile. Preserve focused/native/completion counts and terminal reasons rather than fabricating units from arbitrary deletion. These are installed-build fixture observations; long-run lease accounting still needs the planned audit.

## D012 — Defer callback failures until safe native return

Raising through a native event callback lost original fault details and left cleanup in an invalid stage. The adapter now captures primitive provenance, cooperatively stops at legal stages, and raises at `ScipBackend.optimize()` / `raise_if_failed()`. Unknown or structured exception constructors use `CallbackError` with original identity metadata. Reinitialization resets stop state while internal restarts preserve pending stops/faults. Future workers must use this boundary, discard a faulted adapter, and charge all continued work.

## D013 — Preserve the supplied analytical procedure and bound its claims

Task 3 copies Appendix A into one independently runnable standard-library script. The queue/population transition functions, RNG/seed procedure, delayed-payoff calculation, posterior arithmetic, and illustrative overhead mathematics are unchanged; AST comparison records this privately. Entry-point adaptation returns the reference dictionary and accepts an output path, defaulting to ignored `artifacts/checks/appendix_a.json`. `ra check --suite analytical` loads this same source-checkout copy and records its hash, actual platform, executed suites, and measured diagnostic resource scope. Unsupported suites/phases are explicit failures. A self-review regression demonstrated that Python `-O` skipped the supplied assertions while reporting success; both entry points now reject assertion-disabled execution before producing output.

## D014 — Keep diagnostic credit and evidence outside native solver semantics

The integer-only ledger reserves a fresh lineage ID once, spends only active allowance, and returns unused allowance exactly once on closure/cancellation. Python integers preserve exact mass without overflow; closed IDs cannot be reopened. Split/merge/spawn are compositions of these methods, not additional native work or stopping policies. Frozen synthetic evidence records and administrative references live separately; clones retain the same evidence ID/hash, posterior, bound, and estimate. Additional coupled administration and anti-lease fixtures supplement Appendix A without changing it. These checks establish algebra/bookkeeping invariants only. WP01 remains running until its remaining native correctness/harness requirements are completed and reviewed.

## D015 — Separate lease allowance, completion work and body time

Every positive lease grant receives its own CreditLedger; exhaustion/cancellation returns unused allowance once and never imposes a global node stopping budget. Only distinct completion events for nodes dispatched by that lease spend its allowance. Deadline completions remain visible separately and native counters/events are retained without inventing units from deletion or repeated selection. Actual native restart deletes the old root before exposing the new run identity in the exercised fixture: retain ancestor deletion as the first cancellation reason, plus the subsequent run transition and epoch change. New incumbents and unrelated deletions do not cancel leases.

Body time ends at the supplied next rebid-entry or terminal boundary, rather than at the allowance's final completion. It includes intervening native work and continuation callbacks. Successful continuation scans have their own overhead counter within the body; the next rebid's scan belongs to its administration. Callback entry/end/dispatch and solve-safe-return markers are retained for Task 6 / WP02's disjoint request ledger. Diagnostic timeout requests return a legal live node when the global tree is nonempty. Native wrappers are resolved only inside the adapter.

## D016 — Freeze reproducible candidate support without removing live nodes

Canonical NodeKey ordering makes all-frontier modes and ranking ties reproducible. For bounded pools, each deterministic stratum takes floor(K/5) previously unselected nodes; recorded-state RNG samples the remaining slots without replacement from canonical remaining order. Store ordered records/IDs, canonical ordered-ID SHA-256, strata, before/after RNG states and frontier size. K below 5 uses all live nodes; invalid/nonpositive K and duplicate live keys fail explicitly. These are support/bookkeeping conventions, not fitted policy results.

## D017 — Commit grant validation and rebid boundaries before failure can obscure them

Every new native lease grant must designate a currently live root equal to the policy's returned NodeKey before dispatch. An unavailable initial grant is a callback failure, rather than natural exhaustion of a previously dispatched subtree. Known rebids finalize the prior outcome and record administration before native/frontier scanning. Active leases start with a provisional callback boundary; a discovered rebid closes at that saved entry, and uncertain scan failures retain censored outcomes plus explicit residual intervals without inventing a selected action. A confirmed continuation fault remains body work through safe return. Frozen SelectionBoundary records preserve known/discovered/provisional origin, snapshot/dispatch/end and failure/deadline reasons; controller outcomes retain finalized history independently of later choose success. Residual legal native returns are marked residual and are not new allocated actions. The enclosing safe-return boundary retains cooperative debt beyond the callback.

## D018 — Preserve deterministic original covers and exact arithmetic

`weighted-cover-v2-ordinary-clones` uses a template-local standard-library RNG, canonical sorted CSR incidence, nearly equal index blocks, positive integer costs and unchanged zero-degree columns. Clone counts use the mathematical floor of the declared decimal fraction times final column count; the `.58 × 50 = 29` regression prevents binary-float rounding from changing that recipe. Rare counts round the declared decimal proportion, and block inside counts use exact integer ceiling arithmetic. Record rare rows, inside reductions, base/clone counts, clone sources and bridge-before-clone/perturb order. Original binary coverage and cost sums always use Python integers, so uint8 and int64 overflow cannot silently change feasibility or objective. Assignment checks accept only locked-tolerance rounding; positive affine utility transforms all four references consistently and never silently clips raw progress.

Enumeration remains an explicitly called exponential tiny diagnostic, with measured n=8/10/12/16 evidence. Neither generation nor CLI chooses a hidden exhaustive cutoff or enumerates the 64-column probe grid. The probe configuration describes the initial discovery grid, which may be extended by declared doublings; it is not a selected/frozen population and is forbidden in protected splits.

## D019 — Persist declared structured split ownership and strict generation schemas

Seeds derive by SHA-256 over versioned JSON containing master seed, split label and template index. Instance IDs hash canonical original sparse incidence/costs and versioned lineage; assignment hashes include exact checked original objective and binary vector. A shared sibling-dataset ownership registry covers template IDs, original roots, declared ancestors, derivative parent instance hashes, and exact content hashes. Permutations, integer cost rescalings and repeated solver seeds retain the template's split. An incoming conflict fails before changing registry state. This enforces declared ancestry and exact identity; it does not claim graph-isomorphism detection of deliberately undeclared derivatives. Separate dataset roots require explicit registry reconciliation before freeze.

Only generation schemas are implemented: workload, discovery probes, and the CLI's strict purpose-based schema dispatch. Unknown fields, malformed JSON, duplicate keys, nonfinite values, invalid sampling parameters and invalid family weights fail. Default weights divide total mass equally among present families, then equally among cells/templates within family. Manifests explicitly retain `population_frozen=false`; freeze/protocol/worker schemas remain with their owning tasks. Generation writes original-space JSON and checks file hashes without solving or learning. CLI/types initialization remains free of numerical imports; the future worker must fix threads before numerical imports itself. All current custom selectors and direct native selection passed tiny normal/altered correctness diagnostics; these direct native tests do not implement or claim the cold B0/B1 common-observer baseline.

Task 5's initial uncommitted clone-parent interpretation allowed all base columns, including rare-row-incident bridge columns, following the condensed §7 recipe. The supplied PoC's “ordinary columns” restriction was raised during handoff and resolved by A001 before pilot selection. That initial interpretation and its measurements remain historical artifacts, not the current recipe or a frozen population decision.

## D020 — Restore ordinary-column clone eligibility before pilot selection (14 October 2026)

[Amendment A001](protocol/amendments/0001-ordinary-column-clones.md) restores the supplied ordinary-column restriction omitted from condensed specification §7. Generator version `weighted-cover-v2-ordinary-clones` samples with replacement from base columns without rare-row incidence and never from clones. Fixed final-n floor counts, exact base rare degrees, bridge-before-clone order and floor-one perturbation remain. Lineage records the eligibility rule, actual eligible IDs and A001. A positive clone count with no eligible parent raises `GenerationError` with original seed/count/eligible IDs; no seed is dropped or retried. Zero clones still succeed with an empty eligible set. The fixture with old seed 8 cloned rare-incident column 6; the corrected rule excludes it and preserves final rare degree.

Initial unrestricted-parent diagnostics are separately retained under ignored `artifacts/checks/task5/pre-A001/`; fresh generator/exact/all-selector diagnostics and required integration/full suites validate the corrected recipe. No scientific pilot, model, protected outcome or population freeze existed. An alternative unrestricted-parent interpretation would require a separately versioned recipe and fresh native pilot rather than silently changing the corrected population.


## D021 — Share original observation without replacing native selection

The backend exposes explicit `install_selector=False` for genuine native scheduling. That route installs only the common lightweight progress handler, with no custom node selector, Python frontier scan, feature extraction or ancestry bookkeeping. Applicable Python routes share the same observer and retain their existing custom lifecycle/selection work. Verification uses original CSR/costs, exact integer assignments and content-addressed primitive arrays; transformed features remain separate. Event observation has a terminal polling fallback. Callback faults are still contained until safe return, with numerical alarms preserved through native cleanup. Native parity evidence checks unchanged selector parameters and actual focused trajectories, not merely equal final objectives. Baseline registration remains separate work.

## D022 — Make cold receipt availability authoritative and test each worker clock

Parent timing begins immediately before process launch; absolute launch/deadline is runtime metadata outside scientific hashes. The child fixes thread settings before numerical imports, loads the original instance and builds/checks/submits its anchor within charged time. Three causal ping/receipt brackets test the actual request worker's monotonic comparability. Failed alignment blocks label reconstruction; no untested clock-translation fallback is assumed. Child event/local utility may inform runtime policy, while only validated complete messages received by the parent deadline inform achieved utility. Increasing contiguous sequences, ordered receipts and stable assignment identities reject stale/duplicate output. Late validated gains remain in traces but do not improve the score; raw tolerance-sized deviations remain unrounded/unclipped.

## D023 — Preserve faults, cooperative debt and actual release before ledger completion

Common observation requests cooperative interruption at safe callback boundaries, and SCIP receives the remaining wall-time allowance. Parent watchdog coverage extends through process cleanup after transport closure. Ordinary faults retain valid previously received output; numerical alarms retain a distinct correctness status. Stop request, native safe return, child cleanup and parent wait/reap are separate markers; actual parent reap determines process release and release overshoot. Forced termination leaves duration censored and absent child resource measurements absent. Worker process CPU/RSS and overlapping parent CPU/observation are separate measurements, not additive wall categories. Task 6 explicitly marks the timing partition incomplete: Task 7 owns full disjoint reconciliation, final artifact accounting, atomic manifests/recovery and forced-exit resource completion. Diagnostic watchdog grace is not a frozen scientific grace. General run CLI, model loading and protected phases remain unavailable until their owning implementations.


Attempted launch/deadline markers are recorded before calling `Popen`, so launch failures retain measured parent cost without inventing a child process or resource values. Parent Ctrl-C preserves `external_interrupt` after cleanup and receipt reconstruction; accepted anchor/progress remains eligible, and child termination is followed by reap. These cases share the ordinary immutable-prefix rule rather than dropping delivered results.

## D024 — Preserve resource-exhaustion and signal-exit provenance

Native callback `MemoryError` retains primitive status `oom`; built-in MemoryError is safely reconstructed, while arbitrary subclasses still use the safe fallback exception with their original category and identity. Worker search and cleanup use the same classifier, and teardown-introduced faults retain their metadata and stop timestamp. This identifies observed Python allocation failure; it does not diagnose OS OOM from a signal.

Child TERM/INT/HUP/QUIT exits have `external_interrupt` status when the parent did not request termination. Signal number/name and an unattributed origin remain explicit because return status does not identify the sender. Crash signals retain implementation-failure status; ambiguous signals, including SIGKILL, retain unknown-cause provenance without an OOM inference. Parent watchdog, parent interrupt and parent failure termination requests have separate origins, preserving their existing primary statuses. A prior worker terminal status is retained even if the process subsequently dies by signal. Eligible receipt progress survives, actual reap is recorded, and abrupt signal exits remain censored.

A parent-detected protocol failure takes precedence over independent child signal classification even if the child is already dead and no parent termination request is needed. Parent KeyboardInterrupt likewise retains its own primary status in that scheduling order. Raw signal identity/origin/kind and censoring are still recorded independently; absence of a parent kill request does not erase a detected parent failure.

## D025 — Disjoint request timing and immutable recovery

Use an integer monotonic timing stack with six exclusive categories: startup, native, administration, observation, finalization and residual. Nested diagnostic inference is retained separately. Native optimize excludes Python callback scopes; mandatory progress callbacks and original verification/emission belong to observation. Worker entry-through-cleanup is reconciled exactly; launch, worker-accounted time, terminal/interpreter/reap residual and parent finalization form a separate end-to-end partition. Parent observation/sampling CPU and elapsed overlap worker time and are never added to wall elapsed. Sampled process CPU and RSS are lower-bound observations; terminal CPU omits interpreter tail, and unavailable abrupt-exit resources remain absent.

Attempt UUIDs and the seven specified statuses are immutable record fields. Flush temporary JSON and trace data, then atomically create a non-overwriting final manifest whose digest seals exact bytes and whose inventory seals request/progress/solution/log artifacts. A partial journal stays visible throughout execution and survives interrupted finalization. Recovery checks request identities including code/model/build/config/environment hashes, validates durable partial assignments against original input, replays complete receipt records, refuses active attempts and duplicate IDs, and sums each physical prior attempt once. Native search is never serialized or spliced. A committed OOM, deadline, startup timeout or implementation error is an outcome; external interruption remains eligible for a fresh attempt. Numerical alarms quarantine the entire configuration's claims.

An immutable manifest cannot contain the subsequently measured cost of its own commit. The controller-approved boundary therefore retains (1) the request/reap and pre-manifest accounting endpoint, (2) an immutable publication receipt for manifest flush/commit, and (3) an outer accounting record that brackets the entire publish call, including receipt writing. Nonoverlapping intervals combine to total observed cost; the outer audit write is explicitly report-generation overhead with an unknown tail, measured prospectively by a future batch caller rather than recursively inserted into the request. Incomplete publication records retain an explicit unknown-cost count. This is an operational accounting decision; receipt-gated utility, scientific population and protocol are unchanged.
