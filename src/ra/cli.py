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
    check = subcommands.add_parser("check", help="Run implemented analytical diagnostics")
    check.add_argument("--suite", choices=["analytical"], required=True)
    check.add_argument("--out", type=Path, required=True, help="Private analytical report directory")
    generate = subcommands.add_parser("generate", help="Generate deterministic covers without solving")
    generate.add_argument("--config", type=Path, required=True)
    generate.add_argument("--split", choices=['discovery', 'train', 'validation', 'confirmatory', 'shift'], required=True)
    generate.add_argument("--out", type=Path, help="Output directory (default: data/LABEL)")
    generate.add_argument("--dry-run", action="store_true", help="Validate and describe without writing")
    run = subcommands.add_parser('run', help='Run serial public native/shared controls')
    run.add_argument('--config', type=Path, required=True)
    run.add_argument('--phase', required=True)
    run.add_argument('--out', type=Path)
    run.add_argument('--resume', action='store_true')
    run.add_argument('--dry-run', action='store_true')
    collect = subcommands.add_parser('collect', help='Collect bounded randomized training leases')
    collect.add_argument('--config', type=Path, required=True)
    collect.add_argument('--split', required=True)
    collect.add_argument('--out', type=Path, required=True)
    collect.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    try:
        if args.command == 'collect':
            from ra.collect import collect_traces
            report = collect_traces(args.config, args.split, args.out, dry_run=args.dry_run)
        elif args.command == 'run':
            from ra.runner import run_schedule, schedule_succeeded
            attempts = run_schedule(args.config, args.phase, args.out or Path('artifacts/runs')/args.phase,
                                    resume=args.resume, dry_run=args.dry_run)
            report = {'success': args.dry_run or schedule_succeeded(args.out or Path('artifacts/runs')/args.phase),
                      'dry_run': args.dry_run, 'phase': args.phase, 'attempt_ids':[a.attempt_id for a in attempts],
                      'out':str(args.out or Path('artifacts/runs')/args.phase)}
        elif args.command == "generate":
            from ra.config import load_config
            from ra.data import generate_workload
            raw = load_config(args.config, 'generation')
            report = generate_workload(raw, args.split, args.out, dry_run=args.dry_run)
        elif args.command == "check":
            from ra.checks import run_design_checks
            report = run_design_checks(args.out)
        else:
            report = doctor.discover_environment(args.out, dry_run=args.dry_run)
    except OSError as exc:
        print(f"{args.command} could not read or persist its report: {exc}", file=sys.stderr)
        return 1
    except (AssertionError, RuntimeError, ValueError) as exc:
        print(f"{args.command} failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("dry_run") or report.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
