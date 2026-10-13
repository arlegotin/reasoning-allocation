"""Command-line entry point for the currently implemented project commands."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from ra import doctor


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ra", description="Local reasoning allocation diagnostics")
    subcommands = parser.add_subparsers(dest="command", required=True)
    discover = subcommands.add_parser("doctor", help="Discover hardware and verify native SCIP")
    discover.add_argument("--out", type=Path, required=True, help="Private diagnostic report directory")
    discover.add_argument("--dry-run", action="store_true", help="Describe discovery without running or writing")
    args = parser.parse_args(argv)
    try:
        report = doctor.discover_environment(args.out, dry_run=args.dry_run)
    except OSError as exc:
        print(f"doctor could not persist its report: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("dry_run") or report.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
