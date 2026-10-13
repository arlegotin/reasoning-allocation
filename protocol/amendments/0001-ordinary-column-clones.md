# A001 — Ordinary-column clone eligibility

Date: 14 October 2026. Phase: WP01 implementation, before native workload discovery, fitting, or protocol freeze.

The supplied PoC says to clone ordinary columns in the redundant/rare family. The condensed specification omitted that restriction. The initial uncommitted generator sampled any base column, including columns incident to rare rows, which could increase their final degree and duplicate expensive bridges.

Restore the supplied restriction: an ordinary clone parent is a base column with no rare-row incidence. Keep the specified final-column count, `floor(clone_fraction*n)` clone count, bridge-before-clone cost order, and cost perturbation. Sample eligible parents with replacement so a parent may have multiple administrative copies; clones cannot become parents. Record the rule and eligible IDs in lineage and version the generator accordingly. Positive clone count with no eligible parent is an explicit generation failure; preserve the seed and never silently resample.

Prior diagnostic measurements using unrestricted clone parents are historical implementation checks, not evidence for the final generator. Repeat affected generator, exact-optimum, and native selector checks before accepting WP01. No protected outcomes, learned results, or pilot-selected population have been examined. This correction changes no hypothesis, endpoint, solver operation, or baseline requirement.

If “ordinary” was intended to include rare-incident base columns, this interpretation would need a separately versioned recipe and fresh native pilot. The amendment makes that choice reviewable before any comparative claim.
