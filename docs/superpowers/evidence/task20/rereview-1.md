- **I1 — Required cost/utility reuse presentation is missing** — **ADDRESSED**. `REPORT.md:74` and `REPORT.md:86` now provide separate numerical cost and utility tables over N=1/10/100/1000 against explicitly named B0 native default SCIP. The selected frozen A fitting component is authenticated and matched by asset SHA/path, including membership in historical resource evidence (`src/ra/report.py:634`, `src/ra/report.py:686`); only its 0.109858 s wall component is allocated as wall/N (`src/ra/report.py:697`).
- **I1 scope/claim check** — Complete extra preparation A–B0 remains unavailable; B0 zero covers only the learned-fitting component, and the selected component is neither a total nor a bound (`REPORT.md:76`, `src/ra/report.py:645`). Cold request means remain unchanged over reuse; utility, primary effect and simultaneous interval are repeated unchanged, with the descriptive deadline difference separated from the registered three-deadline effect (`REPORT.md:77`, `REPORT.md:88`, `src/ra/report.py:701`). One fit/60 originals/two timing repeats, conditional uncertainty and unknown tails remain explicit. No warm-service, scientific speedup, positive saving, utility-to-seconds or break-even claim is introduced.

### New Breakage in the Fix Diff

- **None** — 0 Critical, 0 Important, 0 Minor. Inspected only supplied `fb033cf..5dca79c` fix diff, including references/checksums and the controller closure recipe; no full-branch re-review.

### Out-of-Scope Observations

- **None**.

### Checks and Evidence

- **Focused saved evidence verified** — The fix report names `OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 LOKY_MAX_CPU_COUNT=1 .venv/bin/python -m pytest tests/test_report.py -q`. Saved RED shows the expected missing `reuse_presentation` failure (1 failed/28 passed); saved GREEN is pristine, **29 passed in 1.06s** (`docs/superpowers/evidence/task20/fix1-focused.txt:2`). The added regression covers counts, independently recorded selected-fit wall allocations, unavailable complete difference, limited B0 zero component, invariant cold costs/utility/interval and absent break-even (`tests/test_report.py:263`). No suite was rerun.
- **Named read-only probe: saved-reuse-input-and-arithmetic — PASS**. Resolved the concrete provenance/arithmetic doubt by checking all six definition input hashes, selected model hash/path, unique fitted candidate and historical-inventory membership. Verified 109858000 ns wall/109795000 ns CPU, all four wall/N allocations, both 120-physical-request cold means, saved utility difference, exact primary effect/interval across N, reuse-table derivation hash and exact equality with report-build reuse output. This parsed saved bytes only; no solver, fit, bootstrap/inference or reproduction execution.
- **Diff review check** — Read supplied diff; recovered initially truncated sections from that same package. No Git commands, scientific-source mutations, helpers or additional tests. The only write is this requested review report.

### Verdict

- **Fix round: All findings addressed, no new Critical/Important breakage.** Open findings: none. Counts: **0 Critical, 0 Important, 0 Minor**; I1 **ADDRESSED**. Final broad review and archive closure remain controller-owned.
