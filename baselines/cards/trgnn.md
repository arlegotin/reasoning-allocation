# TRGNN (B9 reference)

Version1 disposition: **blocked**. Source/access evidence only. No named-method defeat, CPU-infeasibility or reproduction claim. Component/dependency permissions are distinct from author-model, teacher and checkpoint terms. Paper idea reimplementation is a separate path; no legal conclusion about that path is drawn here.

This JSON is the validated `BaselineCard`; hashes refer to preserved audit bytes, not to a reproduced model. Original regimes are descriptions from those audits; unknown details remain explicit.

```json
{
  "schema_version": 1,
  "id": "trgnn",
  "method": "TRGNN (B9 reference)",
  "status": "blocked",
  "source": {
    "paper_url": "https://proceedings.iclr.cc/paper_files/paper/2025/file/82f625a28d822d2748b9f5c4f9a89bb9-Paper-Conference.pdf",
    "paper_revision": "ICLR2025 conference artifact82f625a28d822d2748b9f5c4f9a89bb9;23pages; exact revision/day unresolved",
    "repository_url": null,
    "commit": null,
    "software_license": null,
    "paper_license": "Unresolved paper terms; paper access is not software/asset permission",
    "inspected": [
      "ConferencePDF Figure2/section5.1 pp6-7;section5.2 p8;section6.1 p9;AppendixD.3 pp19-20;AppendixD.9",
      "https://openreview.net/forum?id=gyvYKLEm8t (browser challenge; API/attachment failure)",
      "https://proceedings.iclr.cc/paper_files/paper/2025/hash/82f625a28d822d2748b9f5c4f9a89bb9-Abstract-Conference.html (paper/supplement/bibtex, no repository disclosed)"
    ]
  },
  "permissions": {
    "code": {
      "status": "unresolved",
      "terms": "Official runnable repository/revision/reuse terms unresolved in bounded primary-route audit. Paper says modifies Labassi code; provenance does not expose TRGNN implementation or grant software reuse.",
      "evidence": [
        {
          "path": "docs/superpowers/evidence/task14/current-selector-access-audit.md",
          "sha256": "cf7432b2840dc8f17179c9e21c46ca8f861bc0091d55fa23ed42c76ab5619e60"
        }
      ]
    },
    "checkpoints": {
      "status": "unresolved",
      "terms": "No runnable official asset route/terms established; no checkpoint downloaded.",
      "evidence": [
        {
          "path": "docs/superpowers/evidence/task14/current-selector-access-audit.md",
          "sha256": "cf7432b2840dc8f17179c9e21c46ca8f861bc0091d55fa23ed42c76ab5619e60"
        }
      ]
    },
    "teacher_assets": {
      "status": "unresolved",
      "terms": "Teacher/data/reward input reuse terms unresolved; paper reward is not a licensed corpus.",
      "evidence": [
        {
          "path": "docs/superpowers/evidence/task14/current-selector-access-audit.md",
          "sha256": "cf7432b2840dc8f17179c9e21c46ca8f861bc0091d55fa23ed42c76ab5619e60"
        }
      ]
    },
    "dependencies": {
      "status": "unresolved",
      "terms": "Complete software dependency permission/pins unresolved without official source; Labassi provenance cannot settle TRGNN modifications.",
      "evidence": [
        {
          "path": "docs/superpowers/evidence/task14/current-selector-access-audit.md",
          "sha256": "cf7432b2840dc8f17179c9e21c46ca8f861bc0091d55fa23ed42c76ab5619e60"
        }
      ]
    }
  },
  "original_regime": {
    "architecture": "Paper graph Q selector; executable architecture/tensor shapes/operators unverified without source.",
    "loss": "Event-based reward combines gap change, optimal-path containment and path-switch steps; executable training details unverified.",
    "depth_weighting": "Unresolved source implementation; do not infer from paper-only access.",
    "teacher": "Optimal-path reward ingredients described; teacher generation/code/data costs unmeasured.",
    "candidate_comparison": "Estimate preselection top5, placeholder padding, choose maximum Q (Figure2,5.1,D.3). Global candidate engineering differs from common pool.",
    "hybrid_handoff": "AppendixD.3 p20: four primal-bound updates then native Breadth-First Search. Section5.2 Eventhdlr NODESOLVED/NODEFOCUSED informs switches. Exact update accounting including initial incumbent and callbacks unverified.",
    "solver": "SCIP8.0.4, defaults with presolve/heuristics enabled (6.1). AppendixD.9 cut/restart-disabled ablation is separate from normal-enhancement regime. Official executable dependencies/callback/build pins unresolved.",
    "hardware": "Reported eightRTX4090/twoEPYC7763 for training (6.1) is not minimum hardware proof. No CPU gate or resource measurement."
  },
  "changes": [],
  "adapted_from": null,
  "configuration": null,
  "entry_point": null,
  "gates": {
    "cpu_inference": {
      "state": "not_run",
      "reason": "Official executable source URL/commit and software reuse terms unresolved; OpenReview challenge/metadata/attachment routes failed; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "cpu_backward": {
      "state": "not_run",
      "reason": "Official executable source URL/commit and software reuse terms unresolved; OpenReview challenge/metadata/attachment routes failed; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "serialization": {
      "state": "not_run",
      "reason": "Official executable source URL/commit and software reuse terms unresolved; OpenReview challenge/metadata/attachment routes failed; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "operators": {
      "state": "not_run",
      "reason": "Official executable source URL/commit and software reuse terms unresolved; OpenReview challenge/metadata/attachment routes failed; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "live_features": {
      "state": "not_run",
      "reason": "Official executable source URL/commit and software reuse terms unresolved; OpenReview challenge/metadata/attachment routes failed; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "hybrid_handoff": {
      "state": "not_run",
      "reason": "Official executable source URL/commit and software reuse terms unresolved; OpenReview challenge/metadata/attachment routes failed; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "tiny_optimum": {
      "state": "not_run",
      "reason": "Official executable source URL/commit and software reuse terms unresolved; OpenReview challenge/metadata/attachment routes failed; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "original_reproduction": {
      "state": "not_run",
      "reason": "Official executable source URL/commit and software reuse terms unresolved; OpenReview challenge/metadata/attachment routes failed; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "cpu_resources": {
      "state": "not_run",
      "reason": "Official executable source URL/commit and software reuse terms unresolved; OpenReview challenge/metadata/attachment routes failed; no authorized port attempted, no measured gate failure",
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
    "Official executable source URL/commit and software reuse terms unresolved; OpenReview challenge/metadata/attachment routes failed",
    "Paper-only four-update counting/event callbacks and exact original build unverified; CPU/operator/live/tiny checks unrun"
  ],
  "evidence": [
    {
      "path": "docs/superpowers/evidence/task14/current-selector-access-audit.md",
      "sha256": "cf7432b2840dc8f17179c9e21c46ca8f861bc0091d55fa23ed42c76ab5619e60"
    }
  ]
}
```
