# Mattick–Mutschler tree RL (B8)

Version1 disposition: **blocked**. Source/access evidence only. No named-method defeat, CPU-infeasibility or reproduction claim. Component/dependency permissions are distinct from author-model, teacher and checkpoint terms. Paper idea reimplementation is a separate path; no legal conclusion about that path is drawn here.

This JSON is the validated `BaselineCard`; hashes refer to preserved audit bytes, not to a reproduced model. Original regimes are descriptions from those audits; unknown details remain explicit.

```json
{
  "schema_version": 1,
  "id": "mattick-mutschler",
  "method": "Mattick–Mutschler tree RL (B8)",
  "status": "blocked",
  "source": {
    "paper_url": "https://arxiv.org/html/2310.00112v2",
    "paper_revision": "2310.00112v1 (2023-09-29), v2 (2024-06-05); final TMLR regime not independently verified",
    "repository_url": "https://github.com/MattAlexMiracle/BranchAndBoundBisim",
    "commit": "199ae6e5c42155aa528951cb93bec9482e03545e",
    "software_license": null,
    "paper_license": "Unresolved paper terms; paper access is not software/asset permission",
    "inspected": [
      "https://github.com/MattAlexMiracle/BranchAndBoundBisim/blob/199ae6e5c42155aa528951cb93bec9482e03545e/SelectTree.py#L114 (114-134 schedule, 142-208 selection/handoff; 16-29 sampling)",
      "https://github.com/MattAlexMiracle/BranchAndBoundBisim/blob/199ae6e5c42155aa528951cb93bec9482e03545e/feature_extractor.pyx#L5 (5-9,66-78,114-159 Cython/capsule)",
      "https://github.com/MattAlexMiracle/BranchAndBoundBisim/blob/199ae6e5c42155aa528951cb93bec9482e03545e/TreeList.py#L66 (66-104 and 182 onward)",
      "https://github.com/MattAlexMiracle/BranchAndBoundBisim/blob/199ae6e5c42155aa528951cb93bec9482e03545e/confs/config.yaml#L4 (4-21 CPU/width/depth)",
      "https://github.com/MattAlexMiracle/BranchAndBoundBisim/blob/199ae6e5c42155aa528951cb93bec9482e03545e/confs/training_scheme/PPO.yaml#L1",
      "https://github.com/MattAlexMiracle/BranchAndBoundBisim/blob/199ae6e5c42155aa528951cb93bec9482e03545e/setup.py#L86 (86-111 Extension list discarded)",
      "https://github.com/MattAlexMiracle/BranchAndBoundBisim/blob/199ae6e5c42155aa528951cb93bec9482e03545e/environment.yml#L90 (90-108 and 118 onward)",
      "https://github.com/MattAlexMiracle/BranchAndBoundBisim/blob/199ae6e5c42155aa528951cb93bec9482e03545e/main.py#L70 (70-94 rollout;185-225 input/training)",
      "https://github.com/MattAlexMiracle/BranchAndBoundBisim/blob/199ae6e5c42155aa528951cb93bec9482e03545e/PPO.py#L1 (CleanRL provenance)"
    ]
  },
  "permissions": {
    "code": {
      "status": "unresolved",
      "terms": "Unresolved author custom code/modification terms. Full pinned tree contains no license/notice filenames; scanned source/config/README found no reuse grant. CleanRL attribution is not a grant for custom files.",
      "evidence": [
        {
          "path": "docs/superpowers/evidence/task14/baseline-source-audit.md",
          "sha256": "4e5681cc53231fe0c46aade8faff02cd78b40454237a17862a3a26b9f0e678ef"
        }
      ]
    },
    "checkpoints": {
      "status": "unresolved",
      "terms": "No checkpoints present in pinned tree; availability/terms elsewhere unresolved. Fresh authorized training would avoid checkpoint reuse, but has not occurred.",
      "evidence": [
        {
          "path": "docs/superpowers/evidence/task14/baseline-source-audit.md",
          "sha256": "4e5681cc53231fe0c46aade8faff02cd78b40454237a17862a3a26b9f0e678ef"
        }
      ]
    },
    "teacher_assets": {
      "status": "unresolved",
      "terms": "No training/evaluation data present in pinned tree. External availability/permissions unresolved; generated fresh data must have distinct originals, optima and charged generation.",
      "evidence": [
        {
          "path": "docs/superpowers/evidence/task14/baseline-source-audit.md",
          "sha256": "4e5681cc53231fe0c46aade8faff02cd78b40454237a17862a3a26b9f0e678ef"
        }
      ]
    },
    "dependencies": {
      "status": "unresolved",
      "terms": "CleanRL MIT at 7e24ae238eab6a8e7efbbf452cb4a8922bcda73f supplies upstream provenance, exact copied file/revision unresolved. Native SCIP/PySCIPOpt/Cython and Torch dependency terms/build pins remain separate from author modifications.",
      "evidence": [
        {
          "path": "docs/superpowers/evidence/task14/baseline-source-audit.md",
          "sha256": "4e5681cc53231fe0c46aade8faff02cd78b40454237a17862a3a26b9f0e678ef"
        }
      ]
    }
  },
  "original_regime": {
    "architecture": "Retained tree representations with 19-feature extractor; source CPU config width512/depth2/one layer/eight rollouts. TreeList probability routines and categorical policy over sorted live IDs. Exact executable architecture not reproduced.",
    "loss": "Clipped PPO with entropy/value coefficients, gradient clipping,16 epochs in source config. No faithful fit performed.",
    "depth_weighting": "Not established by reused audit; source/tree propagation and weighting must be pinned before fidelity claim.",
    "teacher": "RL rollouts rather than Labassi optimal-path imitation; absent info.csv training/eval manifests; default generator screens256 candidates. Generate tiny disjoint optimum-verified inputs before training; charge all screening/rollout attempts.",
    "candidate_comparison": "Filter retained tree distribution to live IDs, sort IDs and sample categorical action. Noninference calls choose best-bound; nodecomp lower-bound ordering. No deterministic max-score substitution.",
    "hybrid_handoff": "Step starts0, increments first; call750 lowers custom standard priority to0 and returns best-bound, inference only through749. Schedule0-250 every call and250-1000 every10; overlap250 uses first range. Prune stored tree every50 calls. Later native selector depends on priorities. Paper v1 4.2/v2 4.3 say250+750 (apparently1000) with v2 longer-budget variant. Source750 and paper1000 are distinct regimes; target version unresolved.",
    "solver": "Original Python3.10.11/PySCIPOpt4.3.0/SCIP8.0.3; Torch2.0.1 CUDA11.7 exported Linux environment, source CPU default. feature_extractor.pyx cimports declarations and accesses SCIP capsule. Recompile against same loaded library; setup.py final cythonize discards configured Extension options. Compiler/ABI failure not executed. Hardcoded Pool(8) and W&B need single-machine/offline adaptation.",
    "hardware": "v2 reports Ryzen7 5800X3D CPU training/experiments around6hours; source CPU default. GPU-only requirement refuted. No minimum RAM/M3 expense/feasibility inferred."
  },
  "changes": [],
  "adapted_from": null,
  "configuration": null,
  "entry_point": null,
  "gates": {
    "cpu_inference": {
      "state": "not_run",
      "reason": "Author-source/modification reuse grant unresolved independently of CleanRL upstream MIT; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "cpu_backward": {
      "state": "not_run",
      "reason": "Author-source/modification reuse grant unresolved independently of CleanRL upstream MIT; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "serialization": {
      "state": "not_run",
      "reason": "Author-source/modification reuse grant unresolved independently of CleanRL upstream MIT; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "operators": {
      "state": "not_run",
      "reason": "Author-source/modification reuse grant unresolved independently of CleanRL upstream MIT; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "live_features": {
      "state": "not_run",
      "reason": "Author-source/modification reuse grant unresolved independently of CleanRL upstream MIT; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "hybrid_handoff": {
      "state": "not_run",
      "reason": "Author-source/modification reuse grant unresolved independently of CleanRL upstream MIT; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "tiny_optimum": {
      "state": "not_run",
      "reason": "Author-source/modification reuse grant unresolved independently of CleanRL upstream MIT; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "original_reproduction": {
      "state": "not_run",
      "reason": "Author-source/modification reuse grant unresolved independently of CleanRL upstream MIT; no authorized port attempted, no measured gate failure",
      "evidence": []
    },
    "cpu_resources": {
      "state": "not_run",
      "reason": "Author-source/modification reuse grant unresolved independently of CleanRL upstream MIT; no authorized port attempted, no measured gate failure",
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
    "Author-source/modification reuse grant unresolved independently of CleanRL upstream MIT",
    "Pinned source750 versus paper250+750 target-regime fidelity unresolved",
    "Original CPU ABI/extractor build, explicit linkage repair and tensor/operator/live/stochastic/handoff gates unrun"
  ],
  "evidence": [
    {
      "path": "docs/superpowers/evidence/task14/baseline-source-audit.md",
      "sha256": "4e5681cc53231fe0c46aade8faff02cd78b40454237a17862a3a26b9f0e678ef"
    }
  ]
}
```
