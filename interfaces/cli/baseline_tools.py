from __future__ import annotations

import argparse
import json
from pathlib import Path

from execution.baseline_manager import FileBaselineStore
from execution.baseline_selector import BaselineSelector
from execution.headless_ledger import FileHeadlessLedger
from execution.promotion_gate import PromotionGate
from execution.run_selector import RunSelector

CANON_HEADLESS_BASELINE_CLI = True


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="businesaios-baseline")
    sub = parser.add_subparsers(dest="command", required=True)

    select_cmd = sub.add_parser("select", help="Select promotable baseline from run ids")
    select_cmd.add_argument("--ledger-dir", default=".runtime/headless_ledger")
    select_cmd.add_argument("--run-id", action="append", required=True)

    promote_cmd = sub.add_parser("promote", help="Promote a run into named baseline")
    promote_cmd.add_argument("--ledger-dir", default=".runtime/headless_ledger")
    promote_cmd.add_argument("--baseline-dir", default=".runtime/headless_baselines")
    promote_cmd.add_argument("--baseline-name", required=True)
    promote_cmd.add_argument("--run-id", required=True)
    promote_cmd.add_argument("--label", default="manual")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.command == "select":
        ledger = FileHeadlessLedger(root_dir=Path(args.ledger_dir))
        records = [ledger.read(run_id) for run_id in args.run_id]
        selector = BaselineSelector(
            promotion_gate=PromotionGate(),
            run_selector=RunSelector(),
        )
        selected = selector.choose(records=records)
        print(json.dumps(selected or {}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if selected else 1

    if args.command == "promote":
        ledger = FileHeadlessLedger(root_dir=Path(args.ledger_dir))
        store = FileBaselineStore(root_dir=Path(args.baseline_dir))
        record = ledger.read(args.run_id)
        store.promote(
            baseline_name=args.baseline_name,
            record=record,
            promoted_at_label=args.label,
            metadata={"via": "cli"},
        )
        print(json.dumps(store.read(baseline_name=args.baseline_name), ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
