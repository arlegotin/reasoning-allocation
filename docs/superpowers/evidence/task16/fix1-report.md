# Task16 fix1 — storage-envelope enforcement

Status: **DONE WITH CONCERNS**, ready for scoped rereview of Important I1. Base: `6f63788bbfb3fe5b571820ac23b4900bbf9559e1`. One writer, current main, no helpers, worktree, scientific retuning or new real experiment. Minor M1 remains deferred to final triage.

## Reproduction and correction

The original orchestration measured attempt directories after execution but checked the accumulated storage only at the next block entry. It omitted new generation, call, progress and finalization metadata. A crossing inside a block could therefore permit another launch, and the final block could publish a success seal while over the envelope. The review's no-solver probe reproduced that branch.

The correction maintains a byte ledger initialized from all existing output files plus the actual external access journal. Each released attempt directory is counted once; coordinator writes add their actual file-size delta, including pointer replacements. It checks observed output after every request and its receipt, before every following launch, and after closure/progress publication. It projects the exact serialized final status, pointer, accounting and new seal before publishing success. An excess follows the existing persistent `resource_alarm` path. Stop diagnostics are retained even if their own bytes exceed the envelope; they do not authorize another worker or a success seal. Existing seals on historical completed resumes are never rewritten.

Attempts, last-valid output, fault flags and cost records are retained. No silent retry is introduced. Completed block records remain evidence that those requests finished even when subsequent metadata growth halts the overall execution; the persistent halt and failed terminal status are authoritative. The implementation avoids rescanning all accumulated raw traces before every request. No broad orchestration refactor was performed.

Final accounting is now prepared before the exact output-size projection. Its scope explicitly marks the subsequent envelope projection and final status/seal/accounting publication as an unmeasured tail. Earlier verification, guards, request work, recovery, metadata publication, audits and final condition sampling remain measured. This limitation is prospective only; no historical A004 cost field was changed or relabelled.

## RED/GREEN evidence

Declared environment for every pytest command: `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=1`.

1. RED, before runtime changes:
   `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=1 .venv/bin/python -m pytest tests/test_confirmatory_execution.py -q -k storage`
   Output: **8 failed, 19 deselected in 4.15s**. Expected failures were excess next-worker calls or missing resource-halt artifacts. Cases cover first/final request output, generation metadata, call metadata, final-block progress, inter-block progress, final accounting and final seal size.
2. GREEN, same command after correction:
   **8 passed, 19 deselected in 3.62s**.
3. Focused regression verification after final source edits:
   `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=1 .venv/bin/python -m pytest tests/test_confirmatory_execution.py tests/test_harness_controls.py -q`
   **55 passed in 99.96s**, exit0, no warnings. Includes ordinary-fault last-valid output/no retry, external/coordinator interruption recovery, live-source rejection, publication/accounting/status, real artificial cold-start queue, and tiny actual native solver coverage.

The new boundary fixtures use small artificial orchestration queues through `_execute_verified`; they deliberately isolate the byte-envelope branch and retain real admission, publication and recovery. They do not claim to be valid standalone scientific freezes. Existing tests exercise full public entry verification and registered full artificial queues. No redundant 718-test suite was run, as explicitly directed by the controller. `git diff --check` passed. Full transcripts are committed as `docs/superpowers/evidence/task16/fix1-{red,green,focused}.txt`.

## Historical and prospective provenance

- Historical A004 runtime commit: `5acc206a8482710578f21ee90bb80ecd8a092828`.
- Historical source hash: `a550040a87910fb4aa710ae9d33578dfd623a0b98b8fda0163dd3fb863557a05`.
- Corrected prospective source hash: `ca2495a7124367afd45761cbd6d6091dbe6fe30a8ad4c70be1c2ce3b4ea34de7`.
- A004 digest remains `72aba9929daa98bb48c64237ebba47e2c6d66e75d65165bf78a0355a53455457`.
- Environment remains `581c89be8c1343d6f925483e82100f4fe81293fea771eedb21aac08a296c5329`; build remains `090e514d7d7581d68bdd17d6880096b12008861c21e34fa31d3d2fa18803cbaf`.

Read-only post-fix verification passed `verify_envelope` and compared all 27 frozen runtime source files with their committed original contents. A004 freeze/digest/protocol/config, execution seal, actual journal and execution audit are byte-identical to the base commit. Strict `verify_protocol(A004)` now rejects with **current executable source/environment/build hash drift**, as required. This check does not launch a worker or append an execution access event. The provenance check took 0.914769042s wall/0.479436s CPU; exact hashes are in `fix1-provenance.json`.

Historical A004 remains 2,520 physical/logical requests, 1,640 complete and 880 deadline, no faults or retries. Its audited 4,591,473,863 output bytes were below the 33,576,268,800-byte envelope; I1 does not establish a violation in that cohort. All original attempts, inputs, freezes and evidence remain preserved. New real public calibration requests: **0**. New real protected requests: **0**. No effects/significance were inspected and no cohort was regenerated.

Any future protected launch under corrected source requires the appropriate source calibration, amendment and freeze. Historical Task17 analysis must authenticate A004's envelope and committed executed source; it must not pretend that this correction executed the existing cohort or weaken live launch guards. Remaining concerns are the explicit prospective accounting tail, previously recorded sensor/cost limitations, local raw-artifact retention and deferred M1 maintainability (runner now 1,195 lines). The fix commit is the commit containing this report and is recorded in the final task handoff.
