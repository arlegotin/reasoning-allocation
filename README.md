# reasoning-allocation

A planned proof of concept for overhead-aware local bidding on bounded SCIP subtree investments. The first workload is generated weighted set cover, compared with native default and tuned SCIP scheduling, matched learned controls, and faithfully reproduced literature methods where feasible.

The repository currently contains the specification and implementation plan. Solver code, dependencies, hardware discovery, training, and experiments have not been executed here. The supplied preparation results remain attributed to the research brief.

- [PoC specification](docs/superpowers/specs/2026-10-13-reasoning-allocation-design.md): scientific scope, correctness and timing contracts, architecture, controls, evaluation gates, and complete analytical reference.
- [Implementation plan](docs/superpowers/plans/2026-10-13-reasoning-allocation.md): 20 tasks covering WP00–WP10, with interfaces, test cases, verification commands, and commit milestones.
- [Progress](PROGRESS.md): current stage and next entry gate.
- [Decisions](DECISIONS.md): assumptions and engineering choices made during specification.

Implementation starts with WP00 environment and native capability discovery. Measured headroom gates learning; a frozen protocol gates confirmation; evidence gates population engineering and transfer. A rigorous negative result or an explicit blocked gate is a valid scoped outcome.

Commands in the documents describe software to implement. They are not available in this checkout yet.
