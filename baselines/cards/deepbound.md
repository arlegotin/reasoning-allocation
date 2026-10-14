# DeepBound (B9 reference)

Version1 disposition: **blocked**. Source/access evidence only. No named-method defeat, CPU-infeasibility or reproduction claim. Component/dependency permissions are distinct from author-model, teacher and checkpoint terms. Paper idea reimplementation is a separate path; no legal conclusion about that path is drawn here.

This JSON is the validated `BaselineCard`; hashes refer to preserved audit bytes, not to a reproduced model. Original regimes are descriptions from those audits; unknown details remain explicit.

```json
{
  "schema_version": 1,
  "id": "deepbound",
  "method": "DeepBound (B9 reference)",
  "status": "blocked",
  "source": {
    "paper_url": "https://arxiv.org/html/2601.16056v1",
    "paper_revision": "2601.16056v1;2026-01-22 15:41:22 UTC",
    "repository_url": null,
    "commit": null,
    "software_license": null,
    "paper_license": "CC BY-NC-SA4.0 for paper only, not software",
    "inspected": [
      "https://arxiv.org/abs/2601.16056 (v1 date/license)",
      "VersionedHTML sections2.1,4,6.2-6.6; inspected abstract/HTML repository links were arXiv support links"
    ]
  },
  "permissions": {
    "code": {
      "status": "unresolved",
      "terms": "Official implementation/revision/software grant unresolved; inspected paper/abstract disclose no author repository. This does not prove source absence.",
      "evidence": [
        {
          "path": "docs/superpowers/evidence/task14/current-selector-access-audit.md",
          "sha256": "cf7432b2840dc8f17179c9e21c46ca8f861bc0091d55fa23ed42c76ab5619e60"
        }
      ]
    },
    "checkpoints": {
      "status": "unresolved",
      "terms": "Checkpoint source/terms unresolved; paper license not checkpoint license.",
      "evidence": [
        {
          "path": "docs/superpowers/evidence/task14/current-selector-access-audit.md",
          "sha256": "cf7432b2840dc8f17179c9e21c46ca8f861bc0091d55fa23ed42c76ab5619e60"
        }
      ]
    },
    "teacher_assets": {
      "status": "unresolved",
      "terms": "Teacher data/code permission unresolved; two full-strong-branching teacher solves per instance are a required charged original regime.",
      "evidence": [
        {
          "path": "docs/superpowers/evidence/task14/current-selector-access-audit.md",
          "sha256": "cf7432b2840dc8f17179c9e21c46ca8f861bc0091d55fa23ed42c76ab5619e60"
        }
      ]
    },
    "dependencies": {
      "status": "unresolved",
      "terms": "Official solver/PySCIPOpt/numerical implementation pins and terms unresolved without source.",
      "evidence": [
        {
          "path": "docs/superpowers/evidence/task14/current-selector-access-audit.md",
          "sha256": "cf7432b2840dc8f17179c9e21c46ca8f861bc0091d55fa23ed42c76ab5619e60"
        }
      ]
    }
  },
  "original_regime": {
    "architecture": "Paper independent fusion models, mean ensemble scores, node/global-bound features and sibling-pair scoring on creation. Executable architecture/hyperparameters/root/one-child behavior unresolved.",
    "loss": "Paper MSE training (6.3-6.6); no executable tensor/backward parity.",
    "depth_weighting": "Unresolved from bounded source-access audit.",
    "teacher": "6.2:solve each instance twice with full-strong branching: optimum then optimal-path labels; later proof-phase nodes negative. Both solves charged.",
    "candidate_comparison": "Global unsolved-node queue selects maximum ensemble score, scoring sibling pairs on creation; original queue/features not common pool.",
    "hybrid_handoff": "6.3-6.6 describe selection to exhaustion/pruning; no fixed-count/incumbent handoff there. Source fallback/callback behavior unresolved.",
    "solver": "2.1:full-strong branching for all evaluated selectors. Common native branching adaptation requires distinct ID/config/evidence; cannot silently alter shared primary solver. Precise SCIP/PySCIPOpt/nonselection parameters unresolved.",
    "hardware": "4:XeonGold6238R/A10080GB reported experiment hardware only; M3 CPU feasibility/cost unmeasured."
  },
  "changes": [],
  "adapted_from": null,
  "configuration": null,
  "entry_point": null,
  "gates": {
    "cpu_inference": {
      "state": "not_run",
      "reason": "Official runnable implementation commit/software grant unresolved in inspected primary sources; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "cpu_backward": {
      "state": "not_run",
      "reason": "Official runnable implementation commit/software grant unresolved in inspected primary sources; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "serialization": {
      "state": "not_run",
      "reason": "Official runnable implementation commit/software grant unresolved in inspected primary sources; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "operators": {
      "state": "not_run",
      "reason": "Official runnable implementation commit/software grant unresolved in inspected primary sources; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "live_features": {
      "state": "not_run",
      "reason": "Official runnable implementation commit/software grant unresolved in inspected primary sources; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "hybrid_handoff": {
      "state": "not_run",
      "reason": "Official runnable implementation commit/software grant unresolved in inspected primary sources; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "tiny_optimum": {
      "state": "not_run",
      "reason": "Official runnable implementation commit/software grant unresolved in inspected primary sources; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "original_reproduction": {
      "state": "not_run",
      "reason": "Official runnable implementation commit/software grant unresolved in inspected primary sources; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "cpu_resources": {
      "state": "not_run",
      "reason": "Official runnable implementation commit/software grant unresolved in inspected primary sources; no authorized port attempted, no measured gate failure",
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
    "Official runnable implementation commit/software grant unresolved in inspected primary sources",
    "Full-strong-branching teacher/evaluation regime cannot be silently replaced by native common branching",
    "Original build/callbacks/architecture/feature timing and CPU/operator/live/tiny checks unrun"
  ],
  "evidence": [
    {
      "path": "docs/superpowers/evidence/task14/current-selector-access-audit.md",
      "sha256": "cf7432b2840dc8f17179c9e21c46ca8f861bc0091d55fa23ed42c76ab5619e60"
    }
  ]
}
```
