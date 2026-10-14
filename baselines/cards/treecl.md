# TreeCL (B9 reference)

Version1 disposition: **blocked**. Source/access evidence only. No named-method defeat, CPU-infeasibility or reproduction claim. Component/dependency permissions are distinct from author-model, teacher and checkpoint terms. Paper idea reimplementation is a separate path; no legal conclusion about that path is drawn here.

This JSON is the validated `BaselineCard`; hashes refer to preserved audit bytes, not to a reproduced model. Original regimes are descriptions from those audits; unknown details remain explicit.

```json
{
  "schema_version": 1,
  "id": "treecl",
  "method": "TreeCL (B9 reference)",
  "status": "blocked",
  "source": {
    "paper_url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6985051",
    "paper_revision": "SSRN6985051 DOI10.2139/ssrn.6985051;posted2026-06-23;27pages; numbered revision/manuscript date unresolved",
    "repository_url": null,
    "commit": null,
    "software_license": null,
    "paper_license": "Indexed primary SSRN record: all rights reserved; no reuse without permission (paper terms only)",
    "inspected": [
      "https://doi.org/10.2139/ssrn.6985051 (fetch failed)",
      "Indexed primarySSRN abstract6985051/terms; live abstract/PDF HTTP403",
      "https://papers.ssrn.com/sol3/Delivery.cfm/2e328288-2bc3-42e7-966e-d12335409c8b-MECA.pdf?abstractid=6985051&mirid=1 (HTTP403)"
    ]
  },
  "permissions": {
    "code": {
      "status": "unresolved",
      "terms": "Official code source/revision/independent software permission unresolved from accessible abstract. Full paper inaccessible through tested routes; no source-absence claim.",
      "evidence": [
        {
          "path": "docs/superpowers/evidence/task14/current-selector-access-audit.md",
          "sha256": "cf7432b2840dc8f17179c9e21c46ca8f861bc0091d55fa23ed42c76ab5619e60"
        }
      ]
    },
    "checkpoints": {
      "status": "unresolved",
      "terms": "Asset access/terms unresolved.",
      "evidence": [
        {
          "path": "docs/superpowers/evidence/task14/current-selector-access-audit.md",
          "sha256": "cf7432b2840dc8f17179c9e21c46ca8f861bc0091d55fa23ed42c76ab5619e60"
        }
      ]
    },
    "teacher_assets": {
      "status": "unresolved",
      "terms": "Full teacher mechanism/asset reuse terms unresolved; abstract supervision does not license corpus.",
      "evidence": [
        {
          "path": "docs/superpowers/evidence/task14/current-selector-access-audit.md",
          "sha256": "cf7432b2840dc8f17179c9e21c46ca8f861bc0091d55fa23ed42c76ab5619e60"
        }
      ]
    },
    "dependencies": {
      "status": "unresolved",
      "terms": "Dependencies/solver build and reuse terms unresolved; no executable source inspected.",
      "evidence": [
        {
          "path": "docs/superpowers/evidence/task14/current-selector-access-audit.md",
          "sha256": "cf7432b2840dc8f17179c9e21c46ca8f861bc0091d55fa23ed42c76ab5619e60"
        }
      ]
    }
  },
  "original_regime": {
    "architecture": "Indexed abstract only:tree-aware contrastive supervision based on lowest common ancestor. Detailed architecture not accessible; none invented.",
    "loss": "Abstract contrasts on/off-optimal-path candidates and uses branching-sequence augmentation; detailed objective unverified.",
    "depth_weighting": "Unresolved; full paper/source inaccessible through tested routes.",
    "teacher": "Abstract optimal-path-consistency supervision; generation/optimum solve details unverified.",
    "candidate_comparison": "Abstract similarity-based comparisons; executable candidate pool/comparator unknown.",
    "hybrid_handoff": "Unresolved from accessible abstract. No incumbent/selection handoff invented.",
    "solver": "Solver/build/branching/callbacks/full regime unknown because full paper fetch failed.",
    "hardware": "Hardware/runtime unknown; no measured CPU feasibility or minimum inferred."
  },
  "changes": [],
  "adapted_from": null,
  "configuration": null,
  "entry_point": null,
  "gates": {
    "cpu_inference": {
      "state": "not_run",
      "reason": "Full primary paper fetch blocked by testedHTTP403/DOI/DNS routes; revision/regime/details unresolved; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "cpu_backward": {
      "state": "not_run",
      "reason": "Full primary paper fetch blocked by testedHTTP403/DOI/DNS routes; revision/regime/details unresolved; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "serialization": {
      "state": "not_run",
      "reason": "Full primary paper fetch blocked by testedHTTP403/DOI/DNS routes; revision/regime/details unresolved; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "operators": {
      "state": "not_run",
      "reason": "Full primary paper fetch blocked by testedHTTP403/DOI/DNS routes; revision/regime/details unresolved; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "live_features": {
      "state": "not_run",
      "reason": "Full primary paper fetch blocked by testedHTTP403/DOI/DNS routes; revision/regime/details unresolved; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "hybrid_handoff": {
      "state": "not_run",
      "reason": "Full primary paper fetch blocked by testedHTTP403/DOI/DNS routes; revision/regime/details unresolved; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "tiny_optimum": {
      "state": "not_run",
      "reason": "Full primary paper fetch blocked by testedHTTP403/DOI/DNS routes; revision/regime/details unresolved; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "original_reproduction": {
      "state": "not_run",
      "reason": "Full primary paper fetch blocked by testedHTTP403/DOI/DNS routes; revision/regime/details unresolved; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "cpu_resources": {
      "state": "not_run",
      "reason": "Full primary paper fetch blocked by testedHTTP403/DOI/DNS routes; revision/regime/details unresolved; no authorized port attempted, no measured gate failure",
      "evidence": []
    }
  },
  "resources": {
    "measured": false,
    "costs": null,
    "failed_attempts": [],
    "notes": "No author-source execution/download/port/teacher/training/inference attempt. CPU feasibility unknown. Existing read-only access failures remain archived evidence; not solver/CPU failures."
  },
  "blockers": [
    "Full primary paper fetch blocked by testedHTTP403/DOI/DNS routes; revision/regime/details unresolved",
    "Indexed paper terms restrict paper reuse; independent official software grant/source commit unresolved",
    "CPU/tensor/operator/live/tiny checks unrun; permission restriction is not performance or hardware failure"
  ],
  "evidence": [
    {
      "path": "docs/superpowers/evidence/task14/current-selector-access-audit.md",
      "sha256": "cf7432b2840dc8f17179c9e21c46ca8f861bc0091d55fa23ed42c76ab5619e60"
    }
  ]
}
```
