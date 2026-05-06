from __future__ import annotations

import argparse
import json

from execution.headless_boot import build_headless_runtime


CANON_HEADLESS_BUSINESS_MEMORY_CLI = True


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="businesaios-memory")
    sub = parser.add_subparsers(dest="command", required=True)

    get_cmd = sub.add_parser("get", help="Get full business operating memory")
    get_cmd.add_argument("--tenant-id", required=True)
    get_cmd.add_argument("--business-id", required=True)

    summary_cmd = sub.add_parser("summary", help="Get compact business memory summary")
    summary_cmd.add_argument("--tenant-id", required=True)
    summary_cmd.add_argument("--business-id", required=True)

    recent_cmd = sub.add_parser("recent-runs", help="Get recent remembered runs")
    recent_cmd.add_argument("--tenant-id", required=True)
    recent_cmd.add_argument("--business-id", required=True)
    recent_cmd.add_argument("--limit", default=10, type=int)

    failures_cmd = sub.add_parser("failures", help="Get recurring failures")
    failures_cmd.add_argument("--tenant-id", required=True)
    failures_cmd.add_argument("--business-id", required=True)

    wins_cmd = sub.add_parser("wins", help="Get recurring wins")
    wins_cmd.add_argument("--tenant-id", required=True)
    wins_cmd.add_argument("--business-id", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    runtime = build_headless_runtime()
    query = runtime.business_memory_query

    if args.command == "get":
        payload = query.get_memory(tenant_id=args.tenant_id, business_id=args.business_id)
    elif args.command == "summary":
        payload = query.get_summary(tenant_id=args.tenant_id, business_id=args.business_id)
    elif args.command == "recent-runs":
        if int(args.limit) < 1:
            raise SystemExit("--limit must be >= 1")
        payload = query.get_recent_runs(tenant_id=args.tenant_id, business_id=args.business_id, limit=args.limit)
    elif args.command == "failures":
        payload = query.get_recurring_failures(tenant_id=args.tenant_id, business_id=args.business_id)
    elif args.command == "wins":
        payload = query.get_recurring_wins(tenant_id=args.tenant_id, business_id=args.business_id)
    else:
        return 2

    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
