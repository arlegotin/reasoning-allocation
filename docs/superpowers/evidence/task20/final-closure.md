# Controller final archive and report closure recipe

Use this only after Task20 review, the final broad review, and any authorized fix wave/scoped rereview have actually closed. The existing `archive-pre-final.json` remains an immutable pre-final snapshot; create a separate final receipt. Do not rerun inference, solvers, clean installation or the full suite merely to close documentation.

1. Append the actual acceptance/review dispositions and final source HEAD to `.superpowers/sdd/2026-10-13-reasoning-allocation/progress.md`. Preserve every `Ruling:` occurrence in order, including Task-prefixed entries, with its cost-if-wrong text. Keep all review/fix reports and controller receipts in SDD. Append closure to the Task20 implementation report only if appropriate; retain its historical implementation/verification status. If changed, copy it to `docs/superpowers/evidence/task20/report.md`.
2. Update **current** closure prose in `PROGRESS.md` and `README.md`. In `configs/report-achieved.json`, update only WP10's package status/reason and the review-pending limitation to the actual outcome. In `docs/superpowers/evidence/task20/coverage.md`, replace its final review-pending sentence with the actual scope/disposition. Do not change scientific limitations, historical source identities, reproduction receipts, or frozen/numeric files.
3. Refresh the `coverage` SHA256 in `configs/report-achieved.json`. If current explanatory prose in `interpretation.md` or `resources.md` changed, refresh only the corresponding `narrative` / `resources_wp10` reference. All immutable input references, including `reuse_fit_card`, remain unchanged. `reuse_definition` changes only if its text/formulas actually change; if so, refresh that reference and the derived reuse table's derivation reference. No final archive receipt is an input to the report builder, so this ordering has no hash cycle.
4. Regenerate current reporting from saved assets:

```sh
PYTHONPATH=src .venv/bin/python -m ra.cli report --manifest protocol/freeze-A004.sha256 --out REPORT.md > docs/superpowers/evidence/task20/report-build.json
```

If the reuse definition changed, regenerate `docs/superpowers/evidence/task20/reuse-table.json` from `report-build.json`'s `reuse_presentation`, keeping its `{derivation: {path, sha256}, data: ...}` structure. Otherwise the table is unchanged. A second saved-asset report build to a fresh path plus `cmp` verifies deterministic prose if desired; this does not run inference.

5. Archive the closed SDD ledger/reviews and updated current documents to a new destination:

```sh
.venv/bin/python checks/task20_archive.py --phase final --out artifacts/audits/task20-final-closure
```

The command creates the sibling `artifacts/audits/task20-final-closure-receipt.json`. It refuses an existing destination. If a prior final snapshot already exists, use a new generation name. Verify every receipt `files` entry against the archived file bytes, and compare `rulings_in_order` to **all** source ledger lines containing `Ruling:`. The current pre-final count is11; use the actual final count if the controller adds a ruling. Only after verification copy the sibling receipt to new versioned `docs/superpowers/evidence/task20/archive-final.json`.

6. Update `docs/superpowers/evidence/task20/retention.json`: set `phase` to the actual final reviewed closure; append the new archive directory/receipt `{path, sha256, bytes}` to `archive_generations`; append that receipt to `immutable_inventory_pointers`; point `sdd_restore_mapping.archive` to the new generation's `sdd`; update `archive_verification` with the actual file/ruling counts, verified status and final phase. Preserve all earlier generations and pointers. If the durable report changed, it will be included by the tracked-file manifest; it is not a report-builder input. Original absolute-path restoration rules remain.
7. Stage all newly created/changed compact evidence first. Regenerate `MANIFEST.sha256` using the exact tracked-file recipe in `REPRODUCE.md` (it excludes itself), verify `shasum -a 256 -c MANIFEST.sha256`, then run `git diff --check`. Commit the closure documentation/checksums. Archive and manifest receipts must not hash themselves; no self-referential commit SHA is required inside the same commit.

Keep the ignored raw/data/model/wheel/source trees and every previous audit generation. Before any scratch cleanup, verify the final archive and its restore mapping cover the final reviews/ledger. Git alone does not retain the large scientific data. Removing scratch is controller-owned after this closure, and is not part of Task20's implementation fix.
