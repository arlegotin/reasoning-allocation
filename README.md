# reasoning-allocation

A planned proof of concept for overhead-aware local bidding on bounded SCIP subtree investments. The first workload is generated weighted set cover, compared with native default and tuned SCIP scheduling, matched learned controls, and faithfully reproduced literature methods where feasible.

The repository contains the specification, implementation plan, environment doctor, analytical checks, and live SCIP lease adapter. WP00 has passed on the target Apple M3 Max: native ARM64 Python 3.12.9, 36 GiB RAM, and PySCIPOpt 6.3.0 using linked SCIP 10.0.2 / SoPlex 8.0.2. Reviewed checks cover credit conservation, evidence separation, bounded leases, candidate pools, restarts, and safe callback failures. Training and allocation comparisons remain unexecuted. The supplied analytical reference has also been reproduced locally.

- [PoC specification](docs/superpowers/specs/2026-10-13-reasoning-allocation-design.md): scientific scope, correctness and timing contracts, architecture, controls, evaluation gates, and complete analytical reference.
- [Implementation plan](docs/superpowers/plans/2026-10-13-reasoning-allocation.md): 20 tasks covering WP00–WP10, with interfaces, test cases, verification commands, and commit milestones.
- [Progress](PROGRESS.md): current stage and next entry gate.
- [Decisions](DECISIONS.md): assumptions and engineering choices made during specification.

WP01's correctness gate has passed, including generated-cover checks against tiny exhaustive optima. WP02's cold parent/worker timing harness is next. Measured headroom gates learning; a frozen protocol gates confirmation; evidence gates population engineering and transfer. A rigorous negative result or an explicit blocked gate is a valid scoped outcome.

`doctor`, `check --suite analytical`, and `generate` are available. Use a native ARM64 Python 3.12 environment on the target Mac; the artifact lock records the resolved macOS wheels.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: --require-hashes -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m pytest -q
.venv/bin/python -m ra.cli doctor --out artifacts/environment
.venv/bin/python -m ra.cli doctor --out artifacts/environment --dry-run
.venv/bin/python -m ra.cli check --suite analytical --out artifacts/checks
.venv/bin/python checks/validate_design.py
.venv/bin/python -m ra.cli generate --config configs/workload_probes.json --split discovery --dry-run
```

The doctor records actual hardware, memory/disk/power, interpreter/native versions, full SCIP parameters, numerical-library configuration, thread settings, and diagnostic timing/RSS. It solves costs `(1,2,1)` with rows `x0+x1 >= 1`, `x1+x2 >= 1`, then independently checks binary feasibility and objective 2, and runs the native capability fixtures. Solver and LP thread limits are one. Dry-run writes nothing; a native failure preserves its report and exits nonzero. Non-ARM64 diagnostics cannot pass the target architecture gate.

Callback-enabled application code must solve through `ScipBackend.optimize()` or check `raise_if_failed()` after direct native operations. Callback faults retain original provenance and make the run fail after safe native return. The terminal propagation-only root's native/completion counter difference is recorded; fixtures establish bounded installed-build evidence rather than universal solver guarantees.

The analytical command reproduces 512 seeded runs and 102,400 coupled decisions, with delayed-payoff, anti-lease, duplication, and conservation checks. Its overhead arithmetic is illustrative. Unsupported suites and assertion-disabled Python fail explicitly; no native performance result is implied.

Generation preserves original incidence, integer costs, lineage, hashes, and split ownership. The probe grid is discovery-only and performs no solving. [Amendment A001](protocol/amendments/0001-ordinary-column-clones.md) records the ordinary-column clone rule before pilot selection.

Reports, wheels, and licenses are generated under ignored `artifacts/`. Raw hardware reports can include machine identifiers; keep them private. Installation and discovery are setup costs, not benchmark results. Other commands in the design remain future work.
