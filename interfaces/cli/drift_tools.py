from __future__ import annotations

import argparse
import json
from pathlib import Path

from execution.baseline_history import FileBaselineHistoryStore
from execution.baseline_manager import FileBaselineStore
from execution.baseline_rollback import BaselineRollbackManager, FileBaselineRollbackStore
from execution.drift_audit_report import DriftAuditReportBuilder
from execution.drift_detector import DriftDetector
from execution.headless_ledger import FileHeadlessLedger
from execution.rollback_audit_timeline import RollbackAuditTimelineBuilder
from execution.run_diff_builder import RunDiffBuilder


CANON_HEADLESS_DRIFT_CLI = True


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="businesaios-drift")
    sub = parser.add_subparsers(dest="command", required=True)

    audit_cmd = sub.add_parser("audit", help="Build drift audit for baseline vs candidate")
    audit_cmd.add_argument("--baseline-dir", default=".runtime/headless_baselines")
    audit_cmd.add_argument("--history-dir", default=".runtime/headless_baseline_history")
    audit_cmd.add_argument("--ledger-dir", default=".runtime/headless_ledger")
    audit_cmd.add_argument("--baseline-name", required=True)
    audit_cmd.add_argument("--candidate-run-id", required=True)

    rollback_cmd = sub.add_parser("rollback", help="Rollback baseline to fallback run")
    rollback_cmd.add_argument("--baseline-dir", default=".runtime/headless_baselines")
    rollback_cmd.add_argument("--history-dir", default=".runtime/headless_baseline_history")
    rollback_cmd.add_argument("--rollback-dir", default=".runtime/headless_baseline_rollbacks")
    rollback_cmd.add_argument("--ledger-dir", default=".runtime/headless_ledger")
    rollback_cmd.add_argument("--baseline-name", required=True)
    rollback_cmd.add_argument("--fallback-run-id", required=True)
    rollback_cmd.add_argument("--reason", required=True)

    timeline_cmd = sub.add_parser("timeline", help="Show rollback audit timeline")
    timeline_cmd.add_argument("--history-dir", default=".runtime/headless_baseline_history")
    timeline_cmd.add_argument("--rollback-dir", default=".runtime/headless_baseline_rollbacks")
    timeline_cmd.add_argument("--baseline-name", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    if args.command == "audit":
        history = FileBaselineHistoryStore(root_dir=Path(args.history_dir))
        baselines = FileBaselineStore(root_dir=Path(args.baseline_dir), history_store=history)
        ledger = FileHeadlessLedger(root_dir=Path(args.ledger_dir))
        baseline = baselines.read(baseline_name=args.baseline_name)
        candidate = ledger.read(args.candidate_run_id)
        drift = DriftDetector().detect(baseline=baseline, candidate=candidate)
        diff = RunDiffBuilder().build(left=dict(baseline.get("record") or {}), right=candidate)
        text = DriftAuditReportBuilder().build(
            baseline_name=args.baseline_name,
            baseline=baseline,
            candidate=candidate,
            drift=drift,
            diff=diff,
        )
        print(text)
        return 0

    if args.command == "rollback":
        history = FileBaselineHistoryStore(root_dir=Path(args.history_dir))
        baselines = FileBaselineStore(root_dir=Path(args.baseline_dir), history_store=history)
        rollbacks = FileBaselineRollbackStore(root_dir=Path(args.rollback_dir))
        ledger = FileHeadlessLedger(root_dir=Path(args.ledger_dir))
        payload = BaselineRollbackManager(
            rollback_store=rollbacks,
            history_store=history,
        ).rollback(
            baseline_store=baselines,
            baseline_name=args.baseline_name,
            fallback_record=ledger.read(args.fallback_run_id),
            reason=args.reason,
            metadata={"via": "cli"},
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if args.command == "timeline":
        history = FileBaselineHistoryStore(root_dir=Path(args.history_dir))
        rollbacks = FileBaselineRollbackStore(root_dir=Path(args.rollback_dir))
        text = RollbackAuditTimelineBuilder().build(
            baseline_name=args.baseline_name,
            rollback_record=rollbacks.read(baseline_name=args.baseline_name),
            history_rows=history.read_all(baseline_name=args.baseline_name),
        )
        print(text)
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
