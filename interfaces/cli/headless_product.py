from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from application.capability.action_capability_matrix import build_action_capability_matrix_payload
from application.headless.models import CEOParticipation, GoalExecutionRequest
from examples.real_headless_scenarios import build_named_scenario, scenario_names
from execution.headless_boot import build_headless_runtime
from interfaces.common.connector_registry_matrix import build_connector_registry_matrix_payload

CANON_HEADLESS_CLI = True


def _write_json_stdout(payload: object) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="businesaios")
    sub = parser.add_subparsers(dest="command", required=True)

    run_cmd = sub.add_parser("run", help="Execute one headless goal")
    run_cmd.add_argument("goal", type=str)
    run_cmd.add_argument("--business-id", required=True, type=str)
    run_cmd.add_argument("--tenant-id", default="default", type=str)
    run_cmd.add_argument("--user-id", default=None, type=str)
    run_cmd.add_argument("--region", default="global", type=str)
    run_cmd.add_argument("--max-steps", default=1, type=int)
    run_cmd.add_argument("--ceo", action="store_true")
    run_cmd.add_argument("--quiet", action="store_true", help="Suppress full JSON report on stdout")
    run_cmd.add_argument("--ceo-horizon", default="30d", type=str)

    scenario_cmd = sub.add_parser("scenario", help="Execute a real scenario")
    scenario_cmd.add_argument("name", choices=scenario_names())
    scenario_cmd.add_argument("--business-id", required=True, type=str)
    scenario_cmd.add_argument("--tenant-id", default="default", type=str)
    scenario_cmd.add_argument("--user-id", default=None, type=str)
    scenario_cmd.add_argument("--quiet", action="store_true", help="Suppress full JSON report on stdout")

    capability_cmd = sub.add_parser("capability-matrix", help="Print the operational capability matrix")
    capability_cmd.add_argument("--action", default="", type=str)
    capability_cmd.add_argument("--only-prod-ready", action="store_true")

    connector_cmd = sub.add_parser("connector-matrix", help="Print honest connector registry truth")
    connector_cmd.add_argument("--domain", default="", type=str)
    connector_cmd.add_argument("--connector", default="", type=str)
    connector_cmd.add_argument("--only-implemented", action="store_true")
    connector_cmd.add_argument("--only-prod-ready", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "capability-matrix":
        matrix = build_action_capability_matrix_payload()
        if getattr(args, 'action', ''):
            wanted = str(args.action or '').strip()
            matrix = [item for item in matrix if str(item.get('action_type') or '') == wanted]
        if getattr(args, 'only_prod_ready', False):
            matrix = [item for item in matrix if bool(item.get('prod_ready'))]
        _write_json_stdout(matrix)
        return 0

    if args.command == "connector-matrix":
        matrix = build_connector_registry_matrix_payload()
        if getattr(args, 'domain', ''):
            wanted_domain = str(args.domain or '').strip()
            matrix = [item for item in matrix if str(item.get('domain') or '') == wanted_domain]
        if getattr(args, 'connector', ''):
            wanted_connector = str(args.connector or '').strip()
            matrix = [item for item in matrix if str(item.get('connector_name') or '') == wanted_connector]
        if getattr(args, 'only_implemented', False):
            matrix = [item for item in matrix if bool(item.get('implemented'))]
        if getattr(args, 'only_prod_ready', False):
            matrix = [item for item in matrix if bool(item.get('production_ready'))]
        _write_json_stdout(matrix)
        return 0

    runtime = build_headless_runtime(entrypoint="headless_cli")

    if args.command == "run":
        request = GoalExecutionRequest(
            goal=args.goal,
            business_id=args.business_id,
            tenant_id=args.tenant_id,
            user_id=args.user_id,
            region=args.region,
            max_steps=args.max_steps,
            ceo=CEOParticipation(
                enabled=bool(args.ceo),
                objective=args.goal,
                horizon=args.ceo_horizon,
            ),
        )
        report = runtime.contract.execute_autopilot(request)
        if not getattr(args, "quiet", False):
            _write_json_stdout(asdict(report))
        return 0 if report.completed else 1

    if args.command == "scenario":
        request = build_named_scenario(
            name=args.name,
            business_id=args.business_id,
            tenant_id=args.tenant_id,
            user_id=args.user_id,
        )
        report = runtime.contract.execute_autopilot(request)
        if not getattr(args, "quiet", False):
            _write_json_stdout(asdict(report))
        return 0 if report.completed else 1

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
