# Resource-bounded reasoning allocation: PoC specification

Date: 13 October 2026. Status: specification for implementation; no solver experiment has been executed by this repository.

This document turns the supplied research brief into a self-contained build contract, including the reference diagnostic in Appendix A. The companion implementation plan will be `../plans/2026-10-13-reasoning-allocation.md`. The brief's reported Linux preparation checks, literature inspections, and supplied-source hash are provenance reported by the user, not evidence produced here. The original S01–S03 documents and attachment are unavailable in this checkout; do not claim their contents were independently inspected. Implementation requires the repository documents and pinned sources for optional baseline reproductions, without additional requirements hidden in the conversation.

## 1. Intent, scope, and success

Build the smallest complete experiment that asks whether a cheap, deadline-conditioned predictor can choose **which live SCIP search subtree to invest in and how many completed main-tree nodes to invest**, improving optimization progress after every execution cost is charged.

The beneficiary solves repeated, related binary optimization instances locally and needs a feasible decision plus an informative bound before a deadline. Weighted set cover is the initial designed research population. It is not assumed to represent an industrial workload.

The primary implementation is a stateful queue over SCIP's existing search. A lease selects a live root and then its descendants for a bounded amount of completed-node work. The policy changes allocation only; it cannot change branching, pruning, propagation, LP solving, cuts, primal heuristics, presolve, tolerances, or solver correctness rules. Search trajectories may differ because node order affects shared solver state.

A complete delivery may be a competitive improvement, a measured overhead boundary, a tightly supported local null result, or a documented blocked capability gate. A successful software build alone establishes no scientific gain.

### Requirements fixed by the brief

- Work on the current branch; make meaningful commits at independently reviewable milestones.
- The core must run on one MacBook Pro with an M3 Max; actual hardware and environment are discovered, not assumed.
- The core requires no remote GPU, paid inference service, second machine, LLM, or PyTorch dependency.
- Primary timed comparisons use one solver worker and one native solver thread at a time.
- The primary endpoint charges a cold end-to-end request, including imports, model loading, setup, verification, observation, and finalization.
- Native default SCIP and seriously tuned native scheduling remain mandatory comparators.
- Training, tuning, unsuccessful attempts, censored work, and deadline overshoot remain visible and costed.
- Allocation scores, credit, multiplicity, native bounds, and evidence are separate state.
- No protected outcome is used for tuning; scientific changes after freeze require an amendment and appropriate fresh confirmation.

### Non-goals and unacceptable outcomes

The core does not implement a full market, independent solver replicas, learned pruning or branching, general probabilistic beliefs, a solver portfolio, or a custom integer solver. It makes no equilibrium, incentive-compatibility, calibrated-belief, rare-truth, patentability, or foundational novelty claim. Winning against uniform allocation, using fewer nodes, or silently weakening SCIP is insufficient. Calling a pooled tabular critic TRGNN, calling an approximation a faithful reproduction, or treating an inaccessible contender as defeated is unacceptable.

## 2. Evidence and claim boundaries

Use four labels in reports: **source finding**, **deduction**, **locally measured check**, and **proposed experiment**. Metareasoning, learned computation value, node selection, duration scheduling, economic agent architectures, and overhead-aware policies are established lineages according to the supplied brief. Novelty remains unresolved.

| Hypothesis | Discriminating evidence | Limit on the conclusion |
| --- | --- | --- |
| H1: local allocation improves the held-out quality–time frontier | Positive simultaneous paired contrasts against the locked mandatory contender set after all overhead | Only the frozen population, builds, fits, and deadlines |
| H1-L: choosing lease duration matters | Adaptive leases beat separately trained one-node, strongest tuned fixed-lease, and native-plunging controls | A fixed-lease win is attributed to fixed leases |
| H2: population representation has a useful implementation tradeoff | Coupled work/output trajectories match; measured time or memory differs | No intrinsic expressive advantage over an equally stateful queue |
| H3-I: funding and copies preserve evidential state | Immutable evidence IDs and native bound/estimate invariants survive adversarial clones | An invariant, not a real-world belief guarantee |
| H4: bounded local features suffice | Local versus pooled/global controls at matched capacity and actual total cost | A global winner weakens locality, not all metareasoning |
| H5: benefit survives distribution shifts | Separately declared size, structure, cost, and difficulty shifts | Synthetic success is not external transfer |

The queue can store the same administrative state, eligible computations, selection kernel, updates, and random stream as a population. Induction then couples every action and output. Administrative copies share evidence/work references. Independent replicas create extra computations and require matched queue states and costs. Representation-only comparisons must preserve trajectories before discussing efficiency.

Reproduce the brief's Appendix A as a future independent diagnostic: 512 seeds, 102,400 matched decisions; delayed-payoff utilities 0.6 versus 1.0 with optimal path `BB`; one-observation posterior 0.8 versus incorrect duplicated-evidence posterior about 0.941176; illustrative overhead ratios 1.12 and 0.84. These are algebra/bookkeeping checks, not SCIP or M3 measurements. Include an anti-lease example as well.

## 3. Optimization and deadline contract

Instances minimize `cᵀx` subject to `Ax >= 1`, with binary `x`, nonempty rows, unique binary incidences, and positive integer costs. Preserve original sparse incidence and costs independently of SCIP transformations. The all-one anchor has `P0 = sum(c)` and `D0 = 0`; constructing, checking, and submitting it is charged for every method.

At deadline `T`, use only the latest independently validated feasible assignment and original-space dual bound available to the parent by `T`. Define

`U(T) = 1 - (P(T) - D(T)) / (P0 - D0)`.

This is normalized primal–dual progress, not a probability. Before any assignment has been published, achieved utility is 0 and the output is unavailable. The evaluation references `P0,D0` do not imply the anchor has already been returned. After publication the anchor is the fallback.

Feasibility and objective checking use original binary assignments and integer arithmetic. Round solver values only within locked integrality tolerance; reject other fractional values. Accumulation uses at least int64 after checking range, or Python integers. Native dual bounds use fixed numerical tolerances and are not independently certified rational proofs. Tiny instances have optima independently established by enumeration.

Do not silently clip invalid objectives, bounds, or utility. A dual bound above the checked primal beyond tolerance is a correctness alarm. Retain raw tolerance-scale deviations; clip only plotting copies. Keep original-space primal/dual utility separate from transformed-space node features. Positive affine objective transformations must transform all four reference/progress values consistently; the anchor denominator remains positive. General MIPLIB metrics are separate unless valid references are available.

### Availability, stopping, and cost

The parent starts its monotonic timer immediately before worker launch. Deadline includes imports, model/instance loading, setup, anchor, solving, verification, trace transmission, and finalization. Worker progress records become available at the parent's receipt timestamp after worker validation. A child's earlier event timestamp cannot make a late record eligible. Duplicate or out-of-order progress records are rejected by sequence/identity rules.

Verify parent/child monotonic comparability during capability discovery. The child uses the shared deadline for cooperative interruption; the parent independently gates receipt time. If alignment cannot be established, implement and test an explicit clock translation with error bounds before lease-label reconstruction; do not assume comparability. No hard-real-time guarantee is made.

Runtime features may use the child's already validated local progress. Training labels and primary results are reconstructed after the request from authoritative parent receipt times. Store both channels with explicit names; future parent receipt knowledge must never become a runtime feature. In offline labels, `U(t)` means parent-available utility at the aligned boundary `t`.

Native operations can overrun. Record stop-request, safe-return, and worker-release times; charge overshoot while disallowing later utility. A parent watchdog uses a pilot-calibrated, frozen grace; watchdog termination leaves duration lower-bound/censored. Long native work is not free node work.

Disjoint elapsed categories are startup/loading/setup; native execution excluding callbacks; feature/pool/scoring/lease administration; mandatory observation/verification/emission; finalization; and unclassified residual. Nested inference and callback timers are diagnostics, not additional summands. Parent observation cost belongs in machine-resource totals, with its timing overlap explicitly identified. Reconcile worker-exclusive durations to worker elapsed and parent-exclusive launch/receipt/release intervals to end-to-end elapsed; do not sum overlapping parent and worker time. Also record CPU seconds, peak RSS bytes, node/LP counts, trace/model bytes, failures, fallback rate, and actual resource release.

A warm persistent-service track is secondary: initialization is charged once over explicit reuse counts, with warm native and learned methods matched. OS-cache-warm subprocesses still count as cold requests under this definition.

## 4. Architecture and project interfaces

Use an editable Python package `ra` under `src/ra`, installed only during implementation. Start compatibility discovery with native ARM64 Python 3.12 and PySCIPOpt 6.3.0; prefer a newer compatible interpreter after the same checks. Resolve NumPy, SciPy, scikit-learn, psutil, and pytest into an exact artifact-hash lock. This candidate is not an installed-environment claim. Optional historical reproductions may need separate environments; matched primary adaptations need a common native build.

The package has these boundaries:

| Area | Ownership |
| --- | --- |
| `types.py`, `config.py`, `provenance.py` | Immutable project records, strict configuration, schemas, canonical hashes and seeds |
| `data.py`, `exact.py`, `checks.py` | Deterministic covers, integer verification/enumeration, analytical diagnostics |
| `doctor.py`, `scip_backend.py` | Hardware/native capability discovery, version-checked native lifetime mapping |
| `observer.py`, `ledger.py` | Validated progress, receipt gating, work credits, disjoint cost partition |
| `leases.py`, `candidates.py`, `features.py` | Lease state machine, candidate pools, declared pre-allocation features |
| `allocators.py`, `models.py`, `collect.py`, `train.py` | Heuristic/learned policies, prediction artifacts, randomized traces, fitting |
| `worker.py`, `runner.py` | Single-request process, serial scheduling, atomic attempts and recovery |
| `pilot.py`, `freeze.py`, `metrics.py`, `stats.py`, `report.py` | Gates, protected manifest, endpoints, clustered inference, generated report |
| `population.py`, `transfer.py` | Gated matched representation and separate-domain experiments |
| `cli.py` | Validated commands with resolved configurations and explicit paths |

Project interfaces are not claims about existing PySCIPOpt methods. Their immutable field contracts are:

```python
NodeKey(epoch: int, number: int)
NodeRecord(key: NodeKey, parent: NodeKey | None, depth: int,
           native_lower_bound: float, native_estimate: float,
           first_seen_selection: int, ancestry_digest: str,
           category: str)  # category is child, sibling, or leaf
DecisionContext(request_id: str, snapshot_ns: int, deadline_ns: int,
                utility_local: float, primal_original: float,
                dual_original: float, lower_bound_transformed: float,
                cutoff_transformed: float, processed_nodes: int,
                frontier_size: int, feature_schema_hash: str)
Allocation(root: NodeKey, node_limit: int, gain_prediction: float,
           seconds_prediction: float, seconds_q90: float | None,
           selection_probability: float | None, policy_state_hash: str)
```

`Allocator.choose(context, candidates, lease_lengths) -> Allocation` consumes primitives only; `Allocator.observe(outcome) -> None` updates administrative history only. `SearchBackend.live_frontier() -> list[NodeRecord]`, `validated_progress() -> tuple[float, float, float]`, and `request_stop() -> None` form the backend boundary. Only the adapter resolves a `NodeKey` to a currently live native node, and only inside callbacks. No allocator retains native wrappers, updates constraints or bounds, prunes, or performs hidden continuation solves.

A safe native checkpoint is a completed request. Do not pickle a live SCIP state or assume prefix replay/counterfactual cloning exists.

## 5. Native node and lease semantics

The Python selector contract returns a mapping with `selnode`; its comparator orders two native nodes. The adapter must validate this against the linked build rather than rely solely on the [node-selector tutorial](https://pyscipopt.readthedocs.io/en/latest/tutorials/nodeselector.html). Event handling has a documented plugin path; check each required exposed event locally using the [event-handler documentation](https://pyscipopt.readthedocs.io/en/latest/tutorials/eventhandler.html).

1. At a callback, acquire current leaves/children/siblings, deduplicate by `(epoch, number)`, and copy primitive records. Capture parent links while valid. Retain ancestors with live-descendant reference counts; a missing link is an error, never an unrelated-descendant fallback.
2. Cancel leases and advance epoch on native restart/reinitialization. Test `nodeinitsol`/`nodeexitsol` and actual native run identity. If Python lacks reliable run identity, a small version-checked bridge to the installed native interface is permitted after ABI/source parity checks. Do not invent `getNRuns()`. Disabling restarts is diagnostic only and cannot pass the production gate.
3. Count deduplicated main-tree completed-node events (`NODEFEASIBLE`, `NODEINFEASIBLE`, `NODEBRANCHED`), not callback invocations. Reconcile installed native counters separately, including root and nodes resolved without LPs. Node deletion without processing consumes no fictitious credit. Subsolver/LP time remains charged, never additional free allowance.
4. Select the leased root first. Continue among its live descendants by greatest depth, smallest current native estimate, smallest native lower bound, then smallest node number. End on completed-node limit, exhaustion, epoch invalidation, cancellation, deadline, or terminal search. A new incumbent does not end a lease.
5. `nodecomp` is side-effect-free and uses immutable depth then node number; greater depth wins and smaller number breaks ties. Dynamic predictions or elapsed time cannot alter heap ordering. `getBestLeaf()` with this comparator is not a native estimate fallback.
6. At timeout request interruption. If the callback still requires a node and the frontier is nonempty, return a legal live node. `None` denotes an empty tree only. Never credit post-deadline progress.

Start with a full-frontier scan. Later children/siblings fast paths and caches must pass coupled chosen-node/lease/work/output trajectory parity before timing, and be shared with applicable Python controls. Native compiled SCIP is never forced to pay a Python scan.

Logical credits reserve a nonnegative node allowance, spend only on completed main-tree work, and return unused allowance exactly once. Spawn/merge/cancel/restart cycles cannot create credit; canceled lineages cannot spend. Wall-time overshoot is explicit debt, not exact credit conservation.

## 6. Candidate pool, features, and policy

### Candidate/action support

Begin with all live nodes. Profile `K = 32, 128, 512, all`. A bounded pool takes `floor(K/5)` unique nodes from each of minimum estimate, minimum lower bound, maximum depth, and greatest age, with node-number ties. Fill remaining slots by recorded-RNG sampling without replacement from unselected nodes. For frontier size at most `K`, use all; for `K < 5`, use all-frontier mode. Unconsidered nodes remain live. Store pool IDs/hash, strata, seed/state, and frontier size. Conditional action propensity has support only within that pool.

Lease lengths start at `1, 2, 4, 8, ...`. Pilot extension stops when longer actions outlast relevant budgets, exhaust subtrees, or cease to distinguish behavior. Freeze observed supported positive lengths, including 1 and a measured delayed-progress length if one exists. No confirmation-time horizon extrapolation.

### Local feature boundary

Version `configs/features.json` with ordered names, units, origins, caps, masks, and preprocessing. Only pre-allocation fields are permitted:

- Node: depth; transformed normalized estimate/bound and their difference; age; child/sibling/leaf category; parent branching-change counts.
- Bounded ancestry summaries: stored parent estimate/bound and differences; root-to-node depth; recent lineage completed work/gain; time since service.
- Task scalars: original dimensions/density; remaining-time fraction and elapsed time; locally validated primal/dual progress; frontier size and completed-node count; time since verified improvement; native incumbent count.
- Action: `log1p(L)`, past-throughput estimate of available work, interactions with remaining time.

No constraint graph, teacher optimum, descendants' future results, selected-action outcome, or post-selection cost is a local input. Record actual dimension; do not hide growing embeddings.

Normalize node features with transformed lower/cutoff bounds. If both references are finite under SCIP's infinity convention, scale by `max(1, abs(cutoff-lower))`; otherwise use `max(1, abs(finite reference))`, with scale 1 if neither is finite. Masks distinguish solver sentinels, missingness, and feature clipping. Never clip a native bound. Validate objective offset/scaling, negative/zero transformed references, and presolve.

Ridge uses training-instance medians and standardization; constant-feature scale is 1. Boosted trees keep missingness explicit. Fit preprocessing on training only. The CPU reference uses float64. A precision optimization needs decision parity or its own policy variant.

### Learned bid

Fit separate ridge or histogram gradient-boosted squared-error regressors for observed gain and lease-body seconds. Optional duration quantile uses the supported quantile-loss path; this functionality is documented in [HistGradientBoostingRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html), but local latency and coverage require measurement.

For each action, rank

`max(0, predicted_gain) / max(c_min, administration_already_spent + predicted_body_seconds)`.

`c_min` is a measured positive timer/invocation floor. Retain raw negative predictions in logs; nonfinite predictions/schema mismatch fail the run. Predict seconds directly, not an exponentiated log target asserted to be an unbiased mean. Model selection uses closed-loop validation utility after overhead, with fitting/tuning expenditure recorded.

At rebid entry `t_entry`, close the preceding lease; record the new decision before scanning. Snapshot features at `t_snapshot`; dispatch at `t_dispatch`. The interval partitions **rebid administration + body until next rebid entry**. Continuation callbacks are body costs; empty-tree/timeout callback administration is still charged. Fit body seconds and add the currently measured administration, so cheap collection policies cannot make learned scoring free.

Filter using predicted q90 **future body** seconds against dispatch-time remaining budget. Past administration is not deducted twice. If no action survives, allow length-1 actions unless expired. If all nonnegative bids are zero, use minimum estimate then lower bound then node number within surviving actions, with validation-selected fixed length or the closest shorter supported surviving length. Positive-bid ties prefer shorter length then smaller node number. This is a project heuristic, not invoking native SCIP default. Deadline checks after scoring can interrupt without starting a new lease; residual administration stays charged.

## 7. Data, learning, and censoring

The deterministic generator exposes a strict `GeneratorCell`: family, final column count, row count, row degree, blocks, cost distribution, clone fraction, rare-row proportion, and bridge multiplier as applicable. Invalid sampling parameters are rejected, never silently substituted. Stable instance IDs hash canonical sparse incidence/costs plus versioned generation lineage.

| Family | Required recipe |
| --- | --- |
| Uniform sparse | Each row samples `d` distinct columns uniformly; integer costs uniform 1–100 |
| Block/community | Index-partition nearly equal blocks; each row samples `ceil(0.8*d)` inside and remainder outside; only undersized-block inside reduction is allowed and recorded; uniform costs or declared Bernoulli mixture of 1–10 and 50–100 |
| Redundant/rare coverage | Mark `max(1, round(0.02*m))` rare rows by template RNG; rare degree `max(1, floor(d/4))`; ordinary rows uniform; create base columns before clones so `n` is final count; clones copy incidence and perturb integer cost by -1/0/1 with floor 1; declared bridge multiplier affects rare incident columns |

The actual clone count is `floor(clone_fraction*n)` and base count is the remainder, a builder choice fixed here for reproducibility. Apply bridge multiplication to base costs before cloning/perturbation; the manifest records this order. Presolve may remove intended stress structure; preserve that finding. Retain zero-degree columns unless common preprocessing removes them for all methods.

Seed namespaces `discovery`, `train`, `validation`, `confirmatory`, `shift` derive from master seed plus split label using SHA-256. Templates and all permutations/rescalings/repeated solver seeds stay in one split. Record lineage and canonical hashes to detect exact and structured derivatives. Default frozen population weights are equal across three families, then equal across retained cells within family.

Native-only discovery starts at 64 columns and doubles, row/column ratios 0.5/1/2, valid degrees 4/8/16, valid block counts 2/4/8. Discovery chooses a finite mixture with nontrivial steerable search and measured resources, retaining easy instances. No learned result may drive population selection. Freeze split identities before fitting; never open protected results before protocol freeze.

At training rebids use a mixture starting at `epsilon=0.2`: uniform node and supported length within the actual pool versus configured heuristic action. The selected heuristic action probability is `(1-epsilon) + epsilon/(pool_size*length_count)`; every other action gets the uniform component. Log exact propensity and RNG. Multiple heuristic behaviors and a learned-policy collection round diagnose deployment shift; all occur in training namespaces.

Postprocess authoritative records to target `G_j = U(min(t_next,T)) - U(t_entry)`. Store endpoint gain separately from eventual natural-completion outcome. Deadline truncation with zero observed gain is not a natural failure; unselected actions have no fabricated outcome. Store end reason, natural completion, deadline censoring, last observation, completion-outcome-known, administration/body/full duration, and overshoot. Kill-censored duration is a lower bound; exclude it from ordinary completed-duration fitting and report sensitivity or fit an explicitly censored model if material.

Retain zero gains and unsuccessful leases. Default training weights give equal total weight to each original instance; lease-weighted fitting is an ablation. This is supervised prediction with conditional randomized support, not an off-policy optimality/causal guarantee. Any later off-policy estimator must predeclare support, positivity, propensity checks, clipping, effective sample size, and uncertainty; unsupported contrasts are not identifiable.

## 8. Baselines and reproduction gates

| ID | Required behavior and role |
| --- | --- |
| B0 | Installed native SCIP default, normal enhancements, common anchor/observer; always reported |
| B1 | Validation-tuned native estimate/plunging and available native best-bound/depth/breadth selectors; actual parameter names/ranges from installed `getParams()` |
| B2 | Shared-adapter FIFO/round-robin regions, uniform random, minimum estimate, minimum bound, deepest, budget-sensitive schedule; diagnostic controls |
| B3 | Same learner/data/features with `L=1`, retrained for that regime |
| B4 | Separately fit/tune supported fixed leases; retain strongest validation-selected contender |
| B5 | Minimum-estimate node choice with learned/adaptive length only |
| B6 | Pooled-frontier tabular context: mean/std/min/max per continuous nonmissing feature, missing fractions, frontier size; matched capacity and best feasible capacity |
| B7 | Labassi graph selector if permitted and reproduced, including its optimal-path teacher and two-feasible-solution handoff |
| B8 | Mattick–Mutschler tree RL if permitted and reproduced, including original 750-selection handoff and faithful CPU port |
| B9 | Accessible faithfully reproduced TRGNN/DeepBound/TreeCL; original regime and common-build adaptation separated |
| D0–D2 | Finite-tested-schedule hindsight envelope, tiny exact metalevel oracle, and coupled population/queue diagnostics; none is a deployable universal oracle |

B2 budget-sensitive scheduling uses minimum estimate with remaining-time bins and validation-fitted fixed lengths, alternating minimum bound every other rebid initially; tune bin thresholds/frequency prospectively. Heuristic confidence is explicitly not a posterior. Beam-like filtering retains all other nodes; true permanently pruning beam search is an incomplete primal treatment with a separate correctness claim.

Mandatory core comparison classes are B0–B6. Native B0 and B1 each have a primary contrast; B3–B5 establish attribution and B6 tests local sufficiency. Freeze individual B2 variants chosen as primary contrasts before testing rather than selecting a winner on confirmation. Stronger reproduced B7–B9 join the registered set; absent methods narrow claims. All applicable methods see identical deadlines, instances, build, nonallocation settings, seeds, primitive observations, and candidate-pool engineering. Global information is an explicit treatment.

Tune native as seriously as learned models. Record validation candidates, costs, failures, expansion/saturation evidence, and stopping reasons rather than equating cheap and expensive configuration counts. Preserve every prespecified independent fit, not a lucky seed. Teacher, preprocessing, graph extraction, and reused-asset costs count.

For every literature baseline create a card: original paper/repository/commit/license; inspected source lines; architecture/loss/teacher/candidate comparison/handoff; exact changes; tensor parity; live feature parity; tiny correctness; original-regime reproduction; common-build adaptation; measured CPU resources. Status is `reproduced`, `adapted`, `approximation`, `blocked`, or `reference_only`. Public visibility is not reuse permission. Large reported training hardware is not proof of a minimum hardware requirement.

The all-one anchor may trigger a two-incumbent handoff early. Preserve the paper-faithful counter and separately tune an explicitly anchor-aware adaptation; retain the stronger adaptation. DeepBound's reported full-strong branching cannot silently change the shared primary solver. Revisit TRGNN/TreeCL access before any contemporary-learned superiority claim.

## 9. Evaluation, freeze, and statistics

Use a separate run at each deadline `T_j` because policies are budget-conditioned. Instance frontier score is `F_i = sum_j w_j * mean_repeats(U_i(T_j))`, using normalized trapezoidal log-budget weights. Three equally log-spaced deadlines have weights 1/4, 1/2, 1/4. Pilot starts at `T0/4,T0,4*T0`, deriving `T0` from robust native cold completion times or distinct progress-event times if completion is censored/startup-dominated. Freeze the calibrated grid; add points only for pilot-observed curvature.

Independent units are original templates. Timing repeats, permutations, nodes, and leases do not increase sample size. Fits are a crossed source of variation; shared native observations remain shared. Stratify by frozen generator cell. Plan sample/fits/repeats from pilot paired variance, training uncertainty, timing uncertainty, desired useful precision, and resource forecast; no prescribed sample count or arbitrary success threshold.

Planning may use `N ≈ ((z_(1-alpha/(2B)) + z_(1-beta))*s_D/delta)^2`, checked with simulation of clustered/crossed pilot summaries. Freeze the chosen counts and useful precision. Insufficient affordable precision is a recorded limitation, not permission to count repeated timings as independent instances.

Final inference uses a stratified template-cluster bootstrap and independently resampled complete fit runs, preserving shared datasets/native results and paired budgets/methods/repeats. Report conditional-on-fit and across-fit intervals; few fits may not support reliable fit-distribution inference. Choose bootstrap repetitions by quantile Monte Carlo stability. Prespecified `B` primary contrasts use Bonferroni-adjusted two-sided intervals with `alpha=0.05`. A claim of improvement over all contenders requires every corresponding lower limit above zero. Secondary/shift claims remain exploratory unless frozen with simultaneous guardrails.

At every deadline report primal-only, dual-only, absolute objectives, raw gap, solved fraction, time to first verified improvement/optimality, gap-time area, failures, overshoot, memory, CPU, native work, administrative fraction, prediction calibration on observed supported actions, and training/tuning/storage costs. An average frontier win with primal regression is a tradeoff. Tight negative, tight-null, and wide inconclusive intervals receive distinct interpretations.

Freeze fails while hardware/native/environment hashes, workload/splits, models/features/support, baseline cards and statuses, complete configurations, deadline weights, sample/fits/repeats, contrasts, bootstrap/guardrail rules, run-order seed, watchdog, exclusion rules, and resource/storage forecast are unresolved. Protected instance assets may be generated mechanically without viewing their outcomes. Store an immutable experiment ID and digest over the full manifest; subsequent scientific changes get numbered amendments and fresh protected evidence where needed.

Training amortization reports extra training/tuning/assets relative to the chosen contender. At matched quality and positive measured per-request time saving, break-even reuse is extra cost divided by time saved. At equal-time utility gains, show reuse cost/utility curves without inventing a conversion rate.

## 10. Execution gates and resource rules

| Package | Entry and decisive artifact | Acceptance / alternative |
| --- | --- | --- |
| WP00 environment/capability | Actual laptop; `environment/*`, `licenses.json`, `capabilities.json` | ARM64 tiny solve, reliable lifecycle/restarts/completion/events/objective conventions; optional baseline blocks only its claim; core failure blocks SCIP route |
| WP01 invariants/exactness | Native smoke; analytical checks independently runnable | Exact conservation/coupling, delayed and anti-lease harness, native tiny optima, lifetime/objective/deadline edges; mismatches are implementation faults |
| WP02 honest harness | WP01; parent/worker traces and harness validation | Receipt-gated scores reconstruct, timers reconcile, injected difference detected, identical-policy null control, observer cost measured |
| WP03 workload/headroom | WP02; frozen finite discovery population and resource forecast | Native-only sizes/schedules show steerable work or concrete delayed-payoff uncertainty; revise proxy prospectively or complete low-headroom report |
| WP04 local bidder | WP03 continue decision; supported randomized traces and model cards | Valid end-to-end local predictions, no runtime continuations, B3–B5 attribution, closed-loop costs; validation is not confirmation |
| WP05 contenders/fairness | Valid harness/headroom; B6 plus baseline cards | Strong tuning and labeled B7–B9 feasibility/reproduction; unresolved contemporaries narrow claim |
| WP06 protocol freeze | WP04/05 complete; pilot design and immutable manifest | Unopened protected outcomes, resolved sample/resource/analysis fields and dry report; otherwise explicitly limited/blocked protocol |
| WP07 confirmation | WP06 and correctness gates | Fixed serial paired requests and one final analysis; no significance-based stopping or tuning |
| WP08 attribution/robustness | WP07 or named earlier diagnostic need | Smallest discriminating tests; coupled representation parity, latency/global/pool controls and shifts; revised claims get new confirmation |
| WP09 transfer/scale | Meaningful primary effect or specific evidence-supported locality/scale prediction; license/resource gates | Frozen and retrained tracks separated; independent-set/MIPLIB metrics never silently pooled |
| WP10 report | Any valid completed/blocked gate, including early stop | Reconstructible report, costs/failures/amendments/licenses/claims and clean local rerun within achieved scope |

Each package updates `PROGRESS.md`, `DECISIONS.md`, and `artifacts/status.json` with artifact hashes and next gate. `status.json` has schema version, current package, per-package status (`not_started`, `running`, `passed`, `stopped`, `blocked`, `skipped`), evidence paths/hashes, reason, and next action. A scientific amendment changes the protocol, not merely this operational status.

Discover `uname -m`, `sw_vers`, memory/CPU `sysctl`, disk `df`, `system_profiler`, `pmset`, Python architecture/executable, memory pressure, and background load without privileged machine changes. Save exact wheels/hashes/metadata/licenses, linked SCIP/LP versions, parameter dump, BLAS/OpenMP configuration, and source revisions. `pip freeze` alone is insufficient. [PySCIPOpt 6.3.0's release metadata](https://pypi.org/project/PySCIPOpt/6.3.0/) lists ARM64 wheels; this is a distribution fact, not a local capability result.

Start with one worker. For optional untimed collection parallelism, admit only from measured available memory, background reserve, coordinator memory, worker p95 RSS, and a recorded safety factor greater than 1. Primary timings remain serial. Reduce concurrency/buffers before prospectively narrowing a workload; never remove only one method's OOM outcomes. Dense float64 scoring memory is `8*K*H*d` bytes per feature buffer; native tree/cuts/LP/ancestry/training copies may dominate. Shard arrays and use memory mapping instead of unbounded Python dictionaries.

Run timed blocks on external power with recorded power mode, stable ventilation/background load, randomized method order, fixed thread settings before imports, and no concurrent training. Do not purge OS caches or subtract estimated observer overhead from outcomes. Measure paired minimal versus diagnostic observer costs on discovery and simplify equally when necessary.

## 11. Persistence, CLI, and failure semantics

Planned directories are `tests/`, `configs/{native,features.json,workload_manifest.json,exploratory.json,confirmatory.json,mandatory_baselines.json}`, `protocol/{confirmatory.md,freeze.sha256,amendments/}`, `baselines/{cards,patches,parity_fixtures}`, `data/{manifests,discovery,train,validation,confirmatory,shift,traces}`, `artifacts/{environment,models,runs,checks,pilot,audits}`, and `results/{exploratory,confirmatory,ablations,transfer}`. Generated large/private/runtime artifacts stay outside Git; compact configuration, schemas, code, cards, and summary evidence are versioned. This documentation-only delivery creates no product scaffolding or dependencies.

Implement `python -m ra.cli` commands `doctor`, `generate`, `check`, `run`, `collect`, `train`, `freeze`, `analyze`, `report`, plus gated `reproduce` and `transfer`. Every command has help, validated input, explicit output, nonzero failure exit, and dry-run support. No command in this spec is asserted to exist yet. Required usage is:

```bash
python -m ra.cli doctor --out artifacts/environment
python -m ra.cli generate --config configs/workload_manifest.json --split discovery
python -m ra.cli check --suite all --out artifacts/checks
python -m ra.cli run --config configs/exploratory.json --phase pilot
python -m ra.cli collect --config configs/exploratory.json --split train
python -m ra.cli train --config configs/exploratory.json --output artifacts/models
python -m ra.cli freeze --config configs/confirmatory.json --out protocol/freeze.sha256
python -m ra.cli run --config configs/confirmatory.json --phase confirmatory --resume
python -m ra.cli analyze --config configs/confirmatory.json --out results/confirmatory
python -m ra.cli report --manifest protocol/freeze.sha256 --out REPORT.md
```

Use schema-versioned IDs, integer nanoseconds, increasing event sequences, and content-addressed solution arrays. Store one immutable manifest per attempt with template/cell/lineage, instance/method/model/code/environment hashes, seeds/threads, budget, timestamps, final available primal/dual/utility, status/error, disjoint timings, resources, overshoot, and prior-attempt link. Lease records include entry/snapshot/dispatch/end, root/parent/epoch, pool IDs/hash, support, selected length/features/predictions/propensity, work, endpoint gain, censoring, and evidence/lineage. Progress stores child/receipt times, sequence, validated original objective/bound, incumbent hash and availability. Training stores split/weight/target/preprocessing/config hashes, every candidate/failed fit, selected artifact, and costs.

Statuses distinguish `complete`, `deadline`, `startup_timeout`, `oom`, `external_interrupt`, `numerical_alarm`, and `implementation_error`. Ordinary method faults retain the last valid available utility and fault flag. A correctness alarm quarantines the affected configuration's scientific claims. No hidden fallback to native is allowed; a fallback is a declared timed policy component.

Flush a temporary attempt directory and atomically publish its completed manifest. Preserve partial/failed attempts. Resume schedules only requests missing a completed valid manifest with identical hashes; reruns get new attempt IDs and retain earlier cost. Mismatched hashes reject resume. Never splice native prefixes across builds/models. An external outage may rerun its entire paired block under frozen rules; OOM/crashes are outcomes, not removable missingness. Reanalysis of immutable traces reproduces values within declared floating tolerance.

## 12. Mandatory robustness and report contract

Core tests cover empty/single frontier; tied/zero/nonfinite bids; infinity sentinels; objective transformations; root/ancestor deletion and restarts; deadline crossing inside scoring/native work; sparse integer overflow; clone/cancel/credit cycles; duplicated evidence/progress; unsupported actions; exact split lineage; delayed delivery; interruption/finalization/resume hash mismatch; and estimator schema/provenance leakage.

Attribution crosses node scoring with one-node, fixed, adaptive duration and native plunging; gain-only versus gain/cost/q90; local versus pooled/global capacity; identical pools/cache/all-frontier diagnostics; injected inference latency and random-latency/shuffled-feature controls; behavior-mixture/support and instance/lease weighting; independent fits; rare/expensive-bridge and anti-lease cases; shifts; cold/warm reuse. Use the smallest discriminating experiment before broad grids. Exploratory findings require a new freeze/cohort before becoming confirmatory claims.

Gate matched population engineering after measured reason to investigate it. Gate external assets after source/license/storage checks, downloading only necessary MIPLIB material; no blanket redistribution permission is assumed. Weighted independent set uses the empty feasible anchor and sum-of-weights upper bound with reversed primal/dual roles. Frozen zero-shot and charged retraining are separate. If node scheduling fails its gate, an independent-run survival portfolio or correlated-observation Bayesian problem requires its own protocol and direct literature controls; neither inherits a SCIP result.

Final `REPORT.md`, `CLAIMS.md`, `REPRODUCE.md`, and `MANIFEST.sha256` must reconstruct tables without chat history. Each headline row states exact competitors, frozen population/deadlines, independent template and fit counts, paired absolute frontier effect with simultaneous interval, primal/dual outcomes, solved/failed counts, actual runtime/overshoot/memory, extra training/tuning, claim level, and caveats. Include negative/null/blocked stages and license/access gaps. Keep methodological distinction, measured gain, and deployment value separate. No stage is executed merely because a document specifies it.

## 13. Source map and builder decisions

This specification is the complete repository implementation authority for the requested PoC. It preserves the supplied brief's WP00–WP10 order and H1/H1-L/H2/H3-I/H4/H5 hypotheses; omitted narrative creates no additional binding implementation requirement. Routine engineering choices within these constraints belong to the builder; changes to scientific requirements follow the amendment process. This session's web check was limited to the four official dependency/interface references linked above. The brief's prior-art claims below are retained as supplied, not independently re-reviewed in this documentation task:

- Metareasoning/value of computation: [Russell–Wefald](https://www.ijcai.org/Proceedings/89-1/Papers/053.pdf), [Selecting Computations](https://arxiv.org/abs/1408.2048), [BMPS](https://arxiv.org/abs/1711.06892), [lazy heuristic evaluation](https://arxiv.org/abs/1305.5030).
- Scheduling/economies: [DAC](https://arxiv.org/abs/2205.13881), [RunAndSchedule2Survive](https://doi.org/10.1145/3737705), [Baum](https://doi.org/10.1023/A:1007593124513), [market architectures](https://arxiv.org/abs/2503.05828), [heuristic duration scheduling](https://arxiv.org/abs/2103.10294).
- Learned selectors: [Yilmaz–Yorke-Smith](https://arxiv.org/abs/2007.03948), [Labassi paper](https://arxiv.org/abs/2210.16934) and [code](https://github.com/ds4dm/learn2comparenodes), [Mattick–Mutschler paper](https://arxiv.org/abs/2310.00112) and [code](https://github.com/MattAlexMiracle/BranchAndBoundBisim), [TRGNN](https://openreview.net/forum?id=gyvYKLEm8t), [DeepBound](https://arxiv.org/abs/2601.16056), [TreeCL](https://doi.org/10.2139/ssrn.6985051).
- Implementation/data: [SCIP](https://www.scipopt.org/), [native estimate source](https://github.com/scipopt/scip/blob/master/src/scip/nodesel_estimate.c), [events source](https://github.com/scipopt/scip/blob/master/src/scip/type_event.h), [MIPLIB](https://miplib.zib.de/download.html), [Apple M3 specifications](https://support.apple.com/en-us/117736). Execution pins source revisions corresponding to installed builds, not mutable `master`.

Builder decisions made here: focused modules and immutable records; clone rounding/order; explicit local-versus-parent progress channels; no live solver checkpoints; artifact-only freeze and atomic attempt authority. These settle routine engineering ambiguity while preserving the brief's measurement rules. Hardware size, deadlines, pool size, supported horizons, tuning grids, model capacity, sample/fits/repeats, watchdog grace, worker admission, and optional baseline feasibility remain **outputs of named gates**, not arbitrary defaults or open questions requiring advance user answers.

## Appendix A: Complete supplied analytical reference

This is the complete standard-library diagnostic supplied in the brief. During Task 3, copy it into `checks/validate_design.py` and execute it; until then its numerical output remains a supplied preparation result. Preserve the transition rules, seed procedure, and calculations for faithful reproduction. The project check runner may wrap it and write a chosen output path; anti-lease and other adversarial cases are additional tests rather than changes to this reference.

```python
"""Small design checks, not SCIP or MacBook performance experiments."""
from __future__ import annotations
import hashlib
import json
import platform
import random
import sys
from functools import lru_cache
from pathlib import Path


def choose(weights: list[tuple[int, int]], r: float) -> int:
    total = sum(w for _, w in weights)
    assert total > 0 and 0 <= r < 1
    target = r * total
    cumulative = 0
    for key, weight in weights:
        cumulative += weight
        if target < cumulative:
            return key
    raise AssertionError('Invalid weights')


def coupling(seed: int, steps: int = 200) -> int:
    rng = random.Random(seed)
    # Administrative copies share one computation and one evidence record.
    copies: dict[int, list[int]] = {i: [100] for i in range(10)}
    queue = {i: 100 for i in range(10)}
    evidence = {i: hashlib.sha256(str(i).encode()).hexdigest() for i in range(10)}
    original_evidence = evidence.copy()
    treasury = spent = decisions = 0
    work_pop = {i: 0 for i in range(10)}
    work_queue = work_pop.copy()
    for step in range(steps):
        if step % 7 == 0:
            p = rng.randrange(10)
            if copies[p]:
                mass = copies[p].pop()
                copies[p] += [mass // 2, mass - mass // 2]
        if step % 43 == 42:
            p = rng.randrange(10)
            treasury += queue[p]
            queue[p] = 0
            copies[p] = []
        if step % 47 == 46 and treasury:
            p = rng.randrange(10)
            queue[p] += treasury
            copies[p].append(treasury)
            treasury = 0
        assert all(sum(copies[p]) == queue[p] for p in queue)
        assert sum(queue.values()) + treasury + spent == 1000
        if sum(queue.values()) == 0:
            break
        r = rng.random()
        p_pop = choose([(p, w) for p in sorted(copies) for w in copies[p]], r)
        p_queue = choose(sorted(queue.items()), r)
        assert p_pop == p_queue
        for j, mass in enumerate(copies[p_pop]):
            if mass:
                copies[p_pop][j] -= 1
                break
        queue[p_queue] -= 1
        spent += 1
        work_pop[p_pop] += 1
        work_queue[p_queue] += 1
        decisions += 1
        assert work_pop == work_queue
        assert evidence == original_evidence
        assert sum(queue.values()) + treasury + spent == 1000
    return decisions


def delayed_reward() -> dict[str, object]:
    def utility(a: int, b: int) -> float:
        return max(0.6 if a >= 1 else 0.0, 1.0 if b >= 2 else 0.0)
    @lru_cache(None)
    def optimal(a: int, b: int, left: int) -> tuple[float, str]:
        if left == 0:
            return utility(a, b), ''
        options = []
        if a < 1:
            v, path = optimal(a + 1, b, left - 1)
            options.append((v, 'A' + path))
        if b < 2:
            v, path = optimal(a, b + 1, left - 1)
            options.append((v, 'B' + path))
        return max(options) if options else (utility(a, b), '')
    a = b = 0
    for _ in range(2):
        choices = []
        if a < 1:
            choices.append((utility(a + 1, b) - utility(a, b), 'A'))
        if b < 2:
            choices.append((utility(a, b + 1) - utility(a, b), 'B'))
        _, selected = max(choices)
        a += selected == 'A'
        b += selected == 'B'
    result = {'greedy_terminal_utility': utility(a, b),
              'optimal_terminal_utility': optimal(0, 0, 2)[0],
              'optimal_path': optimal(0, 0, 2)[1]}
    assert result == {'greedy_terminal_utility': 0.6,
                      'optimal_terminal_utility': 1.0, 'optimal_path': 'BB'}
    return result


def main() -> None:
    decisions = sum(coupling(seed) for seed in range(512))
    # One Bayes update; copying the record must not repeat the observation.
    posterior_once = 0.5 * 0.8 / (0.5 * 0.8 + 0.5 * 0.2)
    posterior_double_counted = 0.5 * 0.8**2 / (0.5 * 0.8**2 + 0.5 * 0.2**2)
    assert abs(posterior_once - 0.8) < 1e-12
    assert posterior_double_counted > posterior_once
    q, c, h = 0.8, 100.0, 40.0  # Illustrative microseconds; not measured hardware.
    results = {
        'environment': {'system': platform.system(), 'machine': platform.machine(),
                        'python': sys.version.split()[0]},
        'queue_population': {'seeds': 512, 'matched_decisions': decisions,
                            'budget_and_evidence_checks': 'passed'},
        'delayed_reward': delayed_reward(),
        'bayes_duplicate': {'single_observation': posterior_once,
                            'incorrect_double_counting': posterior_double_counted},
        'illustrative_overhead': {
            'baseline_work_us': c, 'new_work_fraction': q, 'bid_us': h,
            'time_ratio_lease_1': q * (c + h) / c,
            'time_ratio_lease_8': q * (c + h / 8) / c,
            'maximum_overhead_per_new_node_us': c * (1 / q - 1)}}
    print(json.dumps(results, indent=2))
    Path(__file__).with_name('results.json').write_text(
        json.dumps(results, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
```
