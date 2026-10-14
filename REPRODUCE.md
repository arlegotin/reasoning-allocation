# Reproduce the achieved A004 scope

Run from this repository root on the retained ARM64 macOS/CPython 3.12.9 machine. No chat or original external brief is required. `REPORT.md`, `CLAIMS.md`, `configs/report-achieved.json`, the versioned specification/plan, and authenticated CSV/JSON sources define the achieved scope. A000–A003 are historical: always use **`configs/confirmatory-A004.json` / `protocol/freeze-A004.sha256`** for the completed experiment.

## Rebuild primary tables from saved immutable results

This reads authenticated stored artifacts and writes a report. It does not bootstrap or run solvers:

```sh
PYTHONPATH=src .venv/bin/python -m ra.cli report --manifest protocol/freeze-A004.sha256 --out /tmp/ra-report.md --dry-run
PYTHONPATH=src .venv/bin/python -m ra.cli report --manifest protocol/freeze-A004.sha256 --out /tmp/ra-report.md
cmp REPORT.md /tmp/ra-report.md
shasum -a 256 -c MANIFEST.sha256
```

The generated report contains all six primary effects and intervals, all 21 global deadline/method endpoint/resource rows and every package disposition. Exact physical endpoints, exploratory family/cell/component tables and calibration remain in `results/confirmatory/`. Early-stop reports accept an explicitly labeled JSON manifest with `schema_version: 1`, scope `analytical`, `blocked` or `validation`, package dispositions, hash-addressed references and limitations. They cannot assert completed confirmation.

## Required clean numerical reproduction

The actual WP10 run uses `artifacts/task20/clean-reproduction`. It creates a fresh venv, installs every dependency wheel offline with `--require-hashes` from `requirements.lock`, checks dependency consistency and native binary/full-default-parameter parity, runs analytical/native checks, authenticates/reconstructs all original A004 receipts, recomputes the same 65,536 draws/seed 2026101502/six contrasts, then compares all numeric inference fields at **zero tolerance**. It also compares exact bytes for endpoints, curves, secondary effects, resource summary and calibration. Expected numeric digest is `6339521bccab940fe0ec0546792a3c6012e65644fe7f63a5dde6418717b83d69`.

The command also runs one fresh cold native-default request on the first stored public validation original, with seed17/deadline2,106,828,958 ns/one thread. This is a measured reproducibility check, not a protected repeat or performance comparison. Its prospective schedule, immutable raw request, original-space reconstruction and separate resources are retained.

The following is the complete command used. The output must not already exist. A future authorized reproduction must use a different directory; do not delete or overwrite a failed/partial run to rerun it.

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=1 \
  .venv/bin/python checks/task20_reproduce.py --out artifacts/task20/clean-reproduction
```

This driver never edits `.venv`, historical raw attempts, models, configurations, plots, reports or artifact indexes. Source is loaded through recorded `PYTHONPATH`; no editable install or unpinned dependency resolution occurs. The bootstrap interpreter, `venv`, `ensurepip`/pip and OS are **not hash-installed by this lock**; actual versions and executable paths are recorded separately. A changed executable path/package bootstrap means the overall environment identity can differ while native binary and parameter parity match. No remote service or second machine is required. Unknown setup/development/monitoring and final receipt tails are not zero.

`commands.json` records exact subprocess commands, exit codes, elapsed wall and child CPU. Inner `*-resources.json`, `parity.json`, `numerical-verification.json` and `native-result.json` retain stage identities, costs and limits. These nested resource scopes overlap. The compact versioned reproduction receipt points to all outputs and the exact source revision. Original solver/analysis/presentation revisions remain distinct from reproduction code. A mismatch stops the driver and preserves the evidence; it never chooses another seed or result.

## Qualified figures and checks

Standalone B6 instability annotations are produced in a new directory from stored inference only:

```sh
PYTHONPATH=src MPLCONFIGDIR=artifacts/task17/matplotlib \
  artifacts/task17/plot-env/bin/python checks/task20_presentation.py --out results/handoff
```

The existing isolated plotting environment uses `requirements/analysis-plot.lock`; its package identity and the new derivation manifest are recorded. Historical `results/confirmatory` images/index remain byte-for-byte unchanged. The plotting command refuses an existing destination.

Final covering suite (thread caps avoid host-core-dependent process oversubscription):

```sh
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=1 .venv/bin/python -m pytest -q
.venv/bin/python -m pip check
git diff --check
```

Strict `verify-freeze` live runtime checking intentionally rejects changed current source against historical A004. Do not disable that guard. `report` authenticates the historical envelope; the numerical driver also checks committed original source and sealed raw receipts. No ordinary run command should relaunch A004 under future code.

## Retention and restoration

Keep the entire ignored `artifacts/` and `data/` trees, especially all failures/pre-fix/source snapshots, wheels, model exports/original sklearn assets and protected raw data. Git alone does **not** contain the experimental raw data. `docs/superpowers/evidence/task20/retention.json` maps the retained trees, immutable inventories and audit generations. The frozen-reference audit covers all embedded path/SHA references across historical freeze manifests and confirmatory configs; the original native/request inventories authenticate their descendants. Preserve original Git commits too (`5acc206`, `42a0b88`, `df9df35` and all source revisions in cards).

Historical absolute paths are part of frozen bytes. Restore the repository/artifact tree at `/Users/artemlegotin/Documents/git_alter/reasoning-allocation`, or provide that exact absolute path as a filesystem alias to the restored tree; never edit frozen JSON to relocate it. Restore archived SDD bytes to the original `.superpowers/sdd/2026-10-13-reasoning-allocation` location if historical links are needed. No direct frozen path/SHA reference into SDD was found; all 3,250 directly embedded assets passed the pre-final audit. Durable audit snapshots also retain all required reviews/source audits/hand-offs/controller receipts and the complete 11-ruling ledger.

The pre-final archive explicitly has **review closure pending**. Controller refresh after Task20 review, final broad review, any single fix wave and scoped rereview:

```sh
.venv/bin/python checks/task20_archive.py --phase final --out artifacts/audits/task20-final-closure
```

Use a fresh generation name on later refreshes. Each receipt is a sibling of the copied tree, so it never hashes itself. Before scratch cleanup, copy the new sibling receipt pointer/hash into the final archival receipt, verify its full inventory and ordered rulings, update `PROGRESS.md` closure status and refresh `MANIFEST.sha256` for changed compact deliverables. Archive the final controller ledger and reviews before deleting scratch. Large originals remain retained rather than selectively deleted.

The final full suite also runs in the clean environment without installing the project. For this command, subprocesses need an **absolute** source path:

```sh
PYTHONPATH="$PWD/src" OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=1 \
  artifacts/task20/clean-reproduction/env/bin/python -m pytest -q
```

One Task20 full-suite invocation omitted that path and produced 91 subprocess/import failures (697 passed,106.24s). Its complete transcript and failing test names remain in `docs/superpowers/evidence/task20/full-suite-final-clean.txt`; the corrected invocation is recorded separately. This verification mistake does not alter the successful numerical reproduction, whose driver sets the absolute source path itself. Test-suite fixtures are isolated from the scientific raw trees; verification/development costs remain separate.

The corrected final clean suite passed **788 tests in161.05s**. The historical `analyze` path also owns historical inventory outputs; the WP10 driver instead uses authenticated reconstruction with separate outputs. Use the supplied driver for a future numerical reproduction.

After the controller updates the final archive pointer, refresh the tracked-file checksum manifest (excluding itself), then verify it:

```sh
python3 - <<'PY'
from pathlib import Path
import hashlib, subprocess
names = subprocess.check_output(['git', 'ls-files', '-z']).decode().split('\0')
paths = sorted({name for name in names if name and name != 'MANIFEST.sha256'})
Path('MANIFEST.sha256').write_text(''.join(
    hashlib.sha256(Path(name).read_bytes()).hexdigest() + '  ' + name + '\n'
    for name in paths))
PY
shasum -a 256 -c MANIFEST.sha256
```

Stage any newly created compact receipts first so `git ls-files` includes them. The ignored raw/audit trees are covered by their retained inventory and sibling receipt hashes, not copied into Git. The current pre-final receipt includes the completed implementer report and publication commit; later controller reviews still require the documented final refresh.

Task20 review fix I1 adds separate reuse tables against B0 over N=1/10/100/1000. Only the authenticated selected-fit component is allocated as wall/N; complete extra preparation cost remains unavailable. Cold-request measurements, utilities and primary uncertainty stay fixed. [Reuse definition](docs/superpowers/evidence/task20/reuse-definition.json) binds inputs/formulas; [reuse table](docs/superpowers/evidence/task20/reuse-table.json) preserves exact values. This saved-asset presentation requires no new study or warm-service assumptions.

The [controller closure recipe](docs/superpowers/evidence/task20/final-closure.md) lists the exact status fields, reference hashes, report outputs, archive/retention pointers and checksum refresh order needed after final review.
