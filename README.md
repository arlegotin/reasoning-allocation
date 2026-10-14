# reasoning-allocation

A local SCIP experiment in allocating bounded subtree work using costed learned bids. The completed A004 study found **no registered positive superiority**: A was worse than the shared estimate-L1 control on the conditional primary frontier, while the other directions remained inconclusive. One frozen fitted bundle, 60 original templates, near-ceiling utilities and a failed B6 Monte Carlo diagnostic limit the result.

- [Report](REPORT.md): all six primary comparisons, cold endpoint/resource tables and package dispositions.
- [Claims](CLAIMS.md): supported findings and limits, including blocked contemporary methods and unexecuted transfer.
- [Reproduction](REPRODUCE.md): exact A004 commands, clean hash-installed reproduction, native checks, resource receipts and artifact restoration.
- [Progress](PROGRESS.md) and [decisions](DECISIONS.md): current review status and ordered rulings.
- [Specification](docs/superpowers/specs/2026-10-13-reasoning-allocation-design.md) and [implementation plan](docs/superpowers/plans/2026-10-13-reasoning-allocation.md): methodological requirements and gates.

The implementation includes original-space correctness checks, receipt-based cold deadlines, immutable attempt recovery, local/pooled learned controls, authenticated historical analysis and scope-limited reporting. Native default and publicly tuned SCIP remain explicit competitors. All unsuccessful/pre-fix attempts and their cost limits are retained. A public 36-request latency diagnostic is descriptive; population engineering and transfer were not executed because their entry gates were unmet.

On the measured local ARM64 M3 Max/36 GiB machine, CPython3.12.9/PySCIPOpt6.3.0 links SCIP10.0.2 and SoPlex8.0.2. No paid inference API, GPU, LLM, PyTorch or second machine is required. The hash lock targets native macOS ARM64 wheels. Large raw data, wheels and model assets are ignored by Git and must be retained alongside the repository; Git alone is not a full experimental backup.

To regenerate the final tables from stored immutable results:

```sh
PYTHONPATH=src .venv/bin/python -m ra.cli report \
  --manifest protocol/freeze-A004.sha256 --out /tmp/ra-report.md
```

Use the explicit A004 path. Historical frozen sources/configurations are immutable, and current-code live execution correctly rejects the historical freeze. See `REPRODUCE.md` for the separate numerical reconstruction command. The final controller reviews and archive closure remain pending at this handoff; no merge, push or deployment is implied.
