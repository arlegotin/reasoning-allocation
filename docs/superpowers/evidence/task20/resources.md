# WP10 resource windows

These are separate serial command envelopes. They overlap the inner numerical/native receipts; wall and CPU are different resources. Unknown development/monitoring/final-write tails are not zero.

| Command | Wall s | Child CPU s | Exit |
|---|---:|---:|---:|
| bootstrap | 1.461492958 | 1.292260000 | 0 |
| install | 6.004650875 | 5.818059000 | 0 |
| pip-check | 0.166937041 | 0.159748000 | 0 |
| parity | 1.896167417 | 0.234247000 | 0 |
| analytical | 0.478227375 | 0.473289000 | 0 |
| native-tests | 2.678247000 | 0.945728000 | 0 |
| numerical | 154.621724541 | 130.943129000 | 0 |
| native | 0.646826709 | 0.461121000 | 0 |
| report | 0.550173292 | 0.299969000 | 0 |

The numerical stage separately measured154.560619875s wall,130.735586s process CPU and2,530,426,880bytes peak RSS. The native stage measured0.583316208s wall/0.22064s process CPU, with child CPU0.189916s. The tiny cold native request consumed0.240613625s before publication plus0.00516525s publication, worker CPU0.169908s, peak RSS65,191,936bytes, zero overshoot; these are nested subsets, not extra totals.

Verification costs: initial .venv full suite787 passing149.45s; extra clean full-suite invocation without PYTHONPATH91 failing/697 passing106.24s. Corrected final clean suite is recorded in its own transcript. Pytest durations exclude some launcher/exit work; test CPU and development/monitoring/setup tails were not comprehensively measured. Failed test names and complete diagnostics remain in full-suite-final-clean.txt.

The new qualified figure derivation has its separate measured wall/CPU in results/handoff/derivation.json; figure work is presentation only. Historical Task17 project costs and original attempt inventories were not rewritten.

Corrected final clean suite: **788 passed in161.05s**, pristine, with absolute `PYTHONPATH` and all three thread/process caps. This is the last full suite for the final code; no additional inference or full-suite repetition followed.
