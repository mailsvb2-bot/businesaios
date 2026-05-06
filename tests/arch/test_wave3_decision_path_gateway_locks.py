from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_decision_gateway_and_scheduler_surfaces_hold_single_path_markers() -> None:
    gateway = (ROOT / "runtime" / "decision_gateway.py").read_text(encoding="utf-8")
    scheduler = (ROOT / "runtime" / "self_driving_scheduler.py").read_text(encoding="utf-8")
    assert "CANON_RUNTIME_DECISION_GATEWAY_SINGLE_PATH = True" in gateway
    assert "CANON_RUNTIME_DECISION_GATEWAY_NO_RAW_DECISION_LOGIC = True" in gateway
    assert "CANON_RUNTIME_SELF_DRIVING_SCHEDULER_GATEWAY_ONLY = True" in scheduler
    assert "CANON_RUNTIME_SELF_DRIVING_SCHEDULER_NO_RAW_DECISION_ISSUE = True" in scheduler


def test_root_runtime_decision_surfaces_do_not_bypass_gateway() -> None:
    targets = [
        ROOT / "runtime" / "self_driving_scheduler.py",
        ROOT / "runtime" / "scheduler_parts" / "deploy_flow.py",
        ROOT / "runtime" / "scheduler_parts" / "monitoring.py",
    ]
    violations: list[str] = []
    for path in targets:
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()
        if "request_scheduler_decision_execution" not in text and "issue_runtime_decision" not in text:
            violations.append(f"{rel}:missing_decision_gateway_helper")
        if ".issue(ws)" in text or ".issue(state)" in text or ".decide(" in text:
            violations.append(f"{rel}:raw_decision_call_present")
    assert violations == [], violations
