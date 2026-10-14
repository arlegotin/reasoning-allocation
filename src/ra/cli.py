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
    train = subcommands.add_parser('train', help='Fit local bids and select by cold public validation')
    train.add_argument('--config',type=Path,required=True)
    train.add_argument('--trace-root',type=Path,default=Path('data/traces/train'))
    train.add_argument('--output',type=Path,required=True)
    train.add_argument('--dry-run',action='store_true')
    reproduce = subcommands.add_parser('reproduce', help='Reproduce only an installed, permitted, pinned literature port')
    reproduce.add_argument('--baseline', required=True)
    reproduce.add_argument('--config', type=Path, required=True, help='Mandatory baseline register')
    reproduce.add_argument('--out', type=Path, required=True)
    reproduce.add_argument('--dry-run', action='store_true')
    freeze = subcommands.add_parser('freeze', help='Validate and seal an unopened scientific protocol')
    freeze.add_argument('--config', type=Path, required=True)
    freeze.add_argument('--out', type=Path, required=True)
    freeze.add_argument('--dry-run', action='store_true')
    verify = subcommands.add_parser('verify-freeze', help='Verify all frozen references and current runtime')
    verify.add_argument('--manifest', type=Path, required=True)
    report_parser = subcommands.add_parser('report', help='Public discovery/validation dry report only')
    report_parser.add_argument('--pilot-summary', type=Path, required=True)
    report_parser.add_argument('--design', type=Path, required=True)
    report_parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'freeze':
            from ra.freeze import freeze_protocol
            value = freeze_protocol(args.config, args.out, dry_run=args.dry_run)
            report = {'success':True, 'dry_run':args.dry_run, 'digest':value, 'out':str(args.out)}
        elif args.command == 'verify-freeze':
            from ra.freeze import verify_protocol
            report = verify_protocol(args.manifest)
        elif args.command == 'report':
            from ra.freeze import read
            from ra.stats import write_pilot_report
            report = write_pilot_report(read(args.pilot_summary),read(args.design),args.out)
        elif args.command == 'reproduce':
            from ra.baselines.register import reproduce_baseline
            report = reproduce_baseline(args.baseline, args.config, args.out, dry_run=args.dry_run)
        elif args.command == 'train':
            from ra.train import fit_models
            report = fit_models(args.config,args.trace_root,args.output,dry_run=args.dry_run)
        elif args.command == 'collect':
            from ra.collect import collect_traces
            report = collect_traces(args.config, args.split, args.out, dry_run=args.dry_run)
        elif args.command == 'run':
            from ra.runner import run_schedule, schedule_succeeded
            output = args.out or Path('artifacts/runs')/args.phase
            if args.phase == 'confirmatory':
                from ra.config import frozen_execution_paths
                from ra.runner import execute_frozen
                digest_path, frozen_output = frozen_execution_paths(args.config)
                output = args.out or frozen_output
                attempts = execute_frozen(digest_path, output, resume=args.resume, dry_run=args.dry_run)
            else:
                attempts = run_schedule(args.config, args.phase, output, resume=args.resume, dry_run=args.dry_run)
            report = {'success': args.dry_run or schedule_succeeded(output),
                      'dry_run': args.dry_run, 'phase': args.phase, 'attempt_ids':[a.attempt_id for a in attempts],
                      'out':str(output)}
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
