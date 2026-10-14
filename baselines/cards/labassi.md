# Labassi graph node comparator (B7)

Version1 disposition: **blocked**. Source/access evidence only. No named-method defeat, CPU-infeasibility or reproduction claim. Component/dependency permissions are distinct from author-model, teacher and checkpoint terms. Paper idea reimplementation is a separate path; no legal conclusion about that path is drawn here.

This JSON is the validated `BaselineCard`; hashes refer to preserved audit bytes, not to a reproduced model. Original regimes are descriptions from those audits; unknown details remain explicit.

```json
{
  "schema_version": 1,
  "id": "labassi",
  "method": "Labassi graph node comparator (B7)",
  "status": "blocked",
  "source": {
    "paper_url": "https://arxiv.org/html/2210.16934v1",
    "paper_revision": "2210.16934v1; NeurIPS 2022 proceedings",
    "repository_url": "https://github.com/ds4dm/learn2comparenodes",
    "commit": "da802e8d1e6687ca7b5593e3e0cad42eb4499942",
    "software_license": null,
    "paper_license": "Unresolved paper terms; paper access is not software/asset permission",
    "inspected": [
      "https://github.com/ds4dm/learn2comparenodes/blob/da802e8d1e6687ca7b5593e3e0cad42eb4499942/node_selection/node_selectors.py#L337 (337-428 comparator/counter)",
      "https://github.com/ds4dm/learn2comparenodes/blob/da802e8d1e6687ca7b5593e3e0cad42eb4499942/node_selection/node_selectors.py#L174 (174-233 teacher)",
      "https://github.com/ds4dm/learn2comparenodes/blob/da802e8d1e6687ca7b5593e3e0cad42eb4499942/node_selection/behaviour_gen.py#L45 (45-106 discriminating pairs)",
      "https://github.com/ds4dm/learn2comparenodes/blob/da802e8d1e6687ca7b5593e3e0cad42eb4499942/node_selection/recorders.py#L323 (323-351 and 424-488 static model graph)",
      "https://github.com/ds4dm/learn2comparenodes/blob/da802e8d1e6687ca7b5593e3e0cad42eb4499942/learning/model.py#L45 (45-99 and 149-211)",
      "https://github.com/ds4dm/learn2comparenodes/blob/da802e8d1e6687ca7b5593e3e0cad42eb4499942/learning/train.py#L21 (21-33 BCE/Adam)",
      "https://github.com/ds4dm/learn2comparenodes/blob/da802e8d1e6687ca7b5593e3e0cad42eb4499942/pyscipopt/LICENSE#L1 (1-21 component-only MIT)",
      "https://github.com/ds4dm/learn2comparenodes/blob/da802e8d1e6687ca7b5593e3e0cad42eb4499942/env.yml#L8 (8-23 original environment)",
      "https://github.com/ds4dm/learn2comparenodes/blob/da802e8d1e6687ca7b5593e3e0cad42eb4499942/utils.py#L43 (43-53 original solver changes)"
    ]
  },
  "permissions": {
    "code": {
      "status": "unresolved",
      "terms": "Unresolved sibling author selector/recorder/learner/generator terms. Full tree and text/header/notebook scan found no grant. README citation request does not settle modification/redistribution.",
      "evidence": [
        {
          "path": "docs/superpowers/evidence/task14/baseline-source-audit.md",
          "sha256": "4e5681cc53231fe0c46aade8faff02cd78b40454237a17862a3a26b9f0e678ef"
        }
      ]
    },
    "checkpoints": {
      "status": "unresolved",
      "terms": "Unresolved dataset/weight reuse terms. Blobs not inspected; wrapper MIT cannot license siblings or checkpoints.",
      "evidence": [
        {
          "path": "docs/superpowers/evidence/task14/baseline-source-audit.md",
          "sha256": "4e5681cc53231fe0c46aade8faff02cd78b40454237a17862a3a26b9f0e678ef"
        }
      ]
    },
    "teacher_assets": {
      "status": "unresolved",
      "terms": "Unresolved teacher corpus/instance reuse. Known-optimum solves and recorded pairs would need independently costed authorized inputs.",
      "evidence": [
        {
          "path": "docs/superpowers/evidence/task14/baseline-source-audit.md",
          "sha256": "4e5681cc53231fe0c46aade8faff02cd78b40454237a17862a3a26b9f0e678ef"
        }
      ]
    },
    "dependencies": {
      "status": "unresolved",
      "terms": "Component-only MIT for supplied pyscipopt/LICENSE, notice retention required. Ecole BSD-3-Clause at c77966c75124860d8983e830354a1b4a6751070b is upstream provenance, copied revision unresolved. SCIP and complete CPU Torch/PyG set need independent terms/pins.",
      "evidence": [
        {
          "path": "docs/superpowers/evidence/task14/baseline-source-audit.md",
          "sha256": "4e5681cc53231fe0c46aade8faff02cd78b40454237a17862a3a26b9f0e678ef"
        }
      ]
    }
  },
  "original_regime": {
    "architecture": "Static original-model bipartite graph: six variable features, four constraint features, coefficient edges; branching bounds recursively updated. 32-dimensional embedding; three GraphConv stages; norm graph score and sigmoid pairwise score difference. Dynamic modern LP graph is a different feature regime.",
    "loss": "BCE and Adam in pinned training source; exact weighting/fitting schedule not reproduced.",
    "depth_weighting": "Exact depth weighting not established by reused audit; do not substitute teacher depth tie-break for a training weight. Resolve pinned training/config before any fidelity promotion.",
    "teacher": "Known-optimal-solution ancestor bounds; prefer containing-optimum node, depth tie-break if both contain it, estimate if neither. Prior optimal solves plus discriminating comparison recording/reversed augmentation are charged teacher work.",
    "candidate_comparison": "Cached by SCIP node number, learned pairwise comparator, inherited dummy nodeselect=getBestNode(). Not an independent top-K maximum-score selector.",
    "hybrid_handoff": "n_primal=2, best_primal=inf, primal_changes=0. nodecomp checks counter before strict primal improvement observation (objective sign reversed for maximization). The second-observation comparison still uses learned scores; later comparisons use native estimate. Improvements between comparisons may collapse. Common anchor may count as first observation; event updates/raw feasible-solution counting change behavior. No anchor-aware adaptation implemented; future version needs separate validation/config ID and retain stronger contender.",
    "solver": "Original fork PySCIPOpt 3.0.2/SCIP 7.0, Python3.9; env/script have old CUDA Torch/PyG choices, CPU CLI exists. Original utils disable constraint upgrades and set randomization. Common build is a separate adaptation: Python3.12 removes imp; fork APIs and ABI must be measured.",
    "hardware": "Paper V100/Xeon Gold6126 describes reported training machine only. CPU CLI exists; M3 feasibility and cost unmeasured."
  },
  "changes": [],
  "adapted_from": null,
  "configuration": null,
  "entry_point": null,
  "gates": {
    "cpu_inference": {
      "state": "not_run",
      "reason": "Author-model/teacher/generator reuse grant unresolved; component MIT does not establish sibling permissions; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "cpu_backward": {
      "state": "not_run",
      "reason": "Author-model/teacher/generator reuse grant unresolved; component MIT does not establish sibling permissions; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "serialization": {
      "state": "not_run",
      "reason": "Author-model/teacher/generator reuse grant unresolved; component MIT does not establish sibling permissions; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "operators": {
      "state": "not_run",
      "reason": "Author-model/teacher/generator reuse grant unresolved; component MIT does not establish sibling permissions; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "live_features": {
      "state": "not_run",
      "reason": "Author-model/teacher/generator reuse grant unresolved; component MIT does not establish sibling permissions; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "hybrid_handoff": {
      "state": "not_run",
      "reason": "Author-model/teacher/generator reuse grant unresolved; component MIT does not establish sibling permissions; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "tiny_optimum": {
      "state": "not_run",
      "reason": "Author-model/teacher/generator reuse grant unresolved; component MIT does not establish sibling permissions; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "original_reproduction": {
      "state": "not_run",
      "reason": "Author-model/teacher/generator reuse grant unresolved; component MIT does not establish sibling permissions; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "cpu_resources": {
      "state": "not_run",
      "reason": "Author-model/teacher/generator reuse grant unresolved; component MIT does not establish sibling permissions; no authorized port attempted, no measured gate failure",
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
    "Author-model/teacher/generator reuse grant unresolved; component MIT does not establish sibling permissions",
    "Checkpoint/data permissions unresolved if reused; regenerate authorized data only after code route is resolved",
    "Original CPU dependency/SCIP-fork build, exact depth weighting, tensor/operator/live extraction and anchor/handoff gates unrun"
  ],
  "evidence": [
    {
      "path": "docs/superpowers/evidence/task14/baseline-source-audit.md",
      "sha256": "4e5681cc53231fe0c46aade8faff02cd78b40454237a17862a3a26b9f0e678ef"
    }
  ]
}
```
