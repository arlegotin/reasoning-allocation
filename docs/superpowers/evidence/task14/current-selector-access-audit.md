# Current selector source-access audit

Audit date: 2026-10-14. Scope: TRGNN, DeepBound, TreeCL only. Local authority read: design specification sections 8 and 13 only. This is a source-access and regime audit, not a reproduction result, implementation, or superiority assessment. No tests, solver runs, installs, repository clones, model/assets downloads, commits, author messages, or port work were performed.

## Disposition register

| Contender | Paper access | Official implementation access | Source commit / software license | Runtime evidence | Audit status |
| --- | --- | --- | --- | --- | --- |
| TRGNN | Official proceedings paper and supplemental PDF readable; OpenReview challenged | No official repository discovered through inspected primary links; OpenReview metadata/attachment inaccessible | Unresolved / unresolved | Paper-level regime available; source callbacks/counter unverified | `paper_accessible_code_unresolved` |
| DeepBound | Versioned arXiv HTML and abstract readable | No implementation repository linked in inspected article/abstract | Unresolved / unresolved; paper license separately identified | Paper-level regime available; solver build and callbacks unverified | `paper_accessible_code_not_discovered` |
| TreeCL | Indexed primary abstract/terms readable; live abstract and PDF fetch failed | Not discoverable from available primary abstract; full-paper links cannot be inspected | Unresolved / unresolved | Abstract-level description only | `full_paper_fetch_blocked_permission_restricted` |

These statuses describe this bounded audit. None asserts that source does not exist. None sets a literature card to `reproduced` or `adapted`. Task 14 remains open pending implementation/reproduction or explicit block cards.

## TRGNN

Primary pins: [OpenReview forum gyvYKLEm8t](https://openreview.net/forum?id=gyvYKLEm8t); [official ICLR 2025 record](https://proceedings.iclr.cc/paper_files/paper/2025/hash/82f625a28d822d2748b9f5c4f9a89bb9-Abstract-Conference.html); [conference PDF](https://proceedings.iclr.cc/paper_files/paper/2025/file/82f625a28d822d2748b9f5c4f9a89bb9-Paper-Conference.pdf); [official supplemental PDF](https://proceedings.iclr.cc/paper_files/paper/2025/file/82f625a28d822d2748b9f5c4f9a89bb9-Supplemental-Conference.pdf). Proceedings artifact key: `82f625a28d822d2748b9f5c4f9a89bb9`, 23 pages. This is the conference version; exact submission/revision/publication day is unresolved.

Source evidence from the conference PDF: section 6.1, p9, specifies SCIP 8.0.4 with other parameters default and presolve/heuristics enabled. Figure 2 and section 5.1, pp6–7, describe Estimate candidate preselection, placeholder padding, and maximum-Q selection; Appendix D.3, pp19–20, sets n=5. **Appendix D.3, p20, specifies handoff after four primal-bound updates to Breadth-First Search.** This is the reported counter, distinct from a two-feasible-solution rule. Section 5.2, p8, names PySCIPOpt Eventhdlr with NODESOLVED/NODEFOCUSED for switch timing. Reward combines gap change, optimal-path containment, and path-switch steps. Section 6.1 reports eight RTX4090s and two EPYC7763s for training; Appendix D.9 separately disables cuts/restarts.

Access observations: the official abstract links Paper, Supplemental, and Bibtex, but no repository. Supplemental resolves to another 23-page PDF with the same extracted paper text; no GitHub link found. The paper says its code modifies Labassi code; that is provenance, not access to TRGNN code. OpenReview forum and PDF return a browser verification page. API note/forum and attachment routes fail in the web fetcher; direct shell requests fail DNS under the current network restrictions. These are fetch-route failures, not evidence of missing source.

Unresolved: official source URL, revision SHA, reuse license, OpenReview exact date/version, concrete selector/compare callback implementation, exact four-update accounting (including any initial incumbent), and source parameter pins. Do not infer selector callbacks or a software license from the accessible paper.

## DeepBound

Primary pins: [arXiv abstract](https://arxiv.org/abs/2601.16056); [versioned HTML](https://arxiv.org/html/2601.16056v1). Exact version/date: `2601.16056v1`, 2026-01-22 15:41:22 UTC, from abstract submission history. The abstract's license link resolves to [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/); this is paper licensing, not an independently established software license.

Source evidence: section 2.1 uses full-strong branching for all evaluated selectors. Section 6.2 solves each teacher instance twice with FSB: first obtains the optimum, then labels optimal-path nodes; subsequent proof-phase nodes are negative. Sections 6.3–6.6 describe independent fusion models, mean ensemble scores, MSE training, node/global-bound features, and sibling-pair scoring on creation. The global unsolved-node queue selects maximum score and continues to exhaustion/pruning; no fixed-count/incumbent handoff is described there. Section 4 reports Xeon Gold6238R plus A10080GB for DeepBound experiments. [Versioned paper, sections 2.1, 4, 6.2–6.6](https://arxiv.org/html/2601.16056v1).

Access observations: inspected HTML/abstract disclose no implementation repository; their GitHub links concern arXiv rendering support, not DeepBound. Code-finder UI is not an author repository. No source revision or software reuse permission was established.

Unresolved: official repository and revision/license, precise SCIP/PySCIPOpt build and callback names, all nonselection parameter settings, root/one-child scoring and any source fallback, wall deadline, feature timing/caching, and executable architecture/hyperparameters. FSB is a material original-regime condition. A later common-build adaptation must disclose branching changes; it cannot silently modify the shared primary solver.

## TreeCL

Primary pins: [SSRN abstract 6985051](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6985051); [DOI](https://doi.org/10.2139/ssrn.6985051); [indexed official PDF delivery link](https://papers.ssrn.com/sol3/Delivery.cfm/2e328288-2bc3-42e7-966e-d12335409c8b-MECA.pdf?abstractid=6985051&mirid=1). Indexed SSRN metadata identifies *Learning to Select Nodes in Branch-and-Bound via Tree-Aware Contrastive Learning*, 27 pages, posted 2026-06-23. No numbered revision or exact manuscript date was available.

Source evidence: the primary indexed abstract describes optimal-path-consistency supervision contrasting on/off-path candidates relative to their lowest common ancestor, similarity-based comparisons, and branching-sequence augmentation. The indexed primary record states: “All rights reserved. No reuse allowed without permission.” [SSRN primary record](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6985051).

Access observations: opening the abstract and discovered PDF delivery link returns HTTP403 in the web fetcher; DOI fetch also fails. Search indexing exposes the abstract/terms, not the 27-page manuscript. Shell attempts fail DNS under current network restrictions. The PDF remains inaccessible by these routes; do not claim publication/source absence. No official code repository or independent software license was discovered in the available abstract.

Unresolved: full-paper revision, source URL/revision/permission, actual solver/build/branching/callback/candidate pool/handoff, teacher generation, detailed model/loss, and hardware/runtime conditions. Abstract claims cannot fill those gaps. SSRN's restriction is evidence about the posted paper; no additional conclusion about legal rights to independently implement an idea is drawn.

## Prospective one-M3 CPU gate — not run

Deduction and proposed later gate, not source evidence: reported GPU hardware establishes what authors used, not a minimum machine requirement or impossibility on M3 CPU. Once source and reuse terms are established, freeze source revision, solver/dependencies, original callbacks and handoff; inspect device-specific operations; then measure CPU observation extraction, inference, training/data generation time and peak memory on the user's single M3. Require tensor/live-feature parity and tiny solver correctness before original-regime reproduction; separately record any common-build adaptation. Charge all teacher, preprocessing, graph, and reused-asset costs. No feasibility or resource result has been measured by this audit.

For a later gated claim register, attach this report as access evidence only. Resolve the per-method gaps or write explicit block cards identifying the precise access/permission/runtime obstruction; missing baselines narrow claims and cannot support contemporary learned-selector superiority. No author contact is authorized or has occurred.
