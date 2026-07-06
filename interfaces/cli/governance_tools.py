from __future__ import annotations

import argparse
import json
import sys

from application.governance.governance_service import GovernanceService

CANON_HEADLESS_GOVERNANCE_CLI = True


def _write_text_stdout(text: str) -> None:
    sys.stdout.write(str(text) + "\n")


def _write_json_stdout(payload: object) -> None:
    _write_text_stdout(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="businesaios-governance")
    sub = parser.add_subparsers(dest="command", required=True)

    select_cmd = sub.add_parser("select", help="Select promotable baseline from run ids")
    select_cmd.add_argument("--run-id", action="append", required=True)

    promote_cmd = sub.add_parser("promote", help="Promote a run into named baseline")
    promote_cmd.add_argument("--baseline-name", required=True)
    promote_cmd.add_argument("--run-id", required=True)
    promote_cmd.add_argument("--label", default="manual")

    promote_scenario_cmd = sub.add_parser("promote-scenario", help="Select and promote best run for scenario")
    promote_scenario_cmd.add_argument("--scenario", required=True)
    promote_scenario_cmd.add_argument("--run-id", action="append", required=True)
    promote_scenario_cmd.add_argument("--suffix", default="golden")
    promote_scenario_cmd.add_argument("--label", default="scenario_auto")

    audit_cmd = sub.add_parser("audit", help="Build drift audit for baseline vs candidate")
    audit_cmd.add_argument("--baseline-name", required=True)
    audit_cmd.add_argument("--candidate-run-id", required=True)

    rollback_cmd = sub.add_parser("rollback", help="Rollback baseline to fallback run")
    rollback_cmd.add_argument("--baseline-name", required=True)
    rollback_cmd.add_argument("--fallback-run-id", required=True)
    rollback_cmd.add_argument("--reason", required=True)

    timeline_cmd = sub.add_parser("timeline", help="Show rollback audit timeline")
    timeline_cmd.add_argument("--baseline-name", required=True)

    trend_cmd = sub.add_parser("trend", help="Show drift trend across candidate runs")
    trend_cmd.add_argument("--baseline-name", required=True)
    trend_cmd.add_argument("--candidate-run-id", action="append", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    governance = GovernanceService.build_default()

    if args.command == "select":
        payload = governance.select_baseline(run_ids=args.run_id)
        _write_json_stdout(payload or {})
        return 0 if payload else 1

    if args.command == "promote":
        payload = governance.promote_baseline(
            baseline_name=args.baseline_name,
            run_id=args.run_id,
            label=args.label,
            metadata={"via": "cli"},
        )
        _write_json_stdout(payload)
        return 0

    if args.command == "promote-scenario":
        payload = governance.promote_best_for_scenario(
            scenario=args.scenario,
            run_ids=args.run_id,
            suffix=args.suffix,
            label=args.label,
            metadata={"via": "cli"},
        )
        _write_json_stdout(payload or {})
        return 0 if payload else 1

    if args.command == "audit":
        payload = governance.audit_drift(
            baseline_name=args.baseline_name,
            candidate_run_id=args.candidate_run_id,
        )
        _write_text_stdout(payload["report_text"])
        return 0

    if args.command == "rollback":
        payload = governance.rollback_baseline(
            baseline_name=args.baseline_name,
            fallback_run_id=args.fallback_run_id,
            reason=args.reason,
            metadata={"via": "cli"},
        )
        _write_json_stdout(payload)
        return 0

    if args.command == "timeline":
        _write_text_stdout(governance.rollback_timeline(baseline_name=args.baseline_name))
        return 0

    if args.command == "trend":
        payload = governance.drift_trend(
            baseline_name=args.baseline_name,
            candidate_run_ids=args.candidate_run_id,
        )
        _write_json_stdout(payload)
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
