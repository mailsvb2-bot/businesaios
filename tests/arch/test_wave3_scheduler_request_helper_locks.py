from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_scheduler_surfaces_use_single_request_helper() -> None:
    helper = (ROOT / "runtime" / "scheduler_parts" / "decision_request.py").read_text(encoding="utf-8")
    assert "CANON_RUNTIME_SCHEDULER_DECISION_REQUEST_SINGLE_PATH = True" in helper
    assert "CANON_RUNTIME_SCHEDULER_DECISION_REQUEST_GATEWAY_ONLY = True" in helper

    targets = [
        ROOT / "runtime" / "self_driving_scheduler.py",
        ROOT / "runtime" / "scheduler_parts" / "deploy_flow.py",
        ROOT / "runtime" / "scheduler_parts" / "monitoring.py",
    ]
    violations: list[str] = []
    for path in targets:
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT).as_posix()
        if "request_scheduler_decision_execution" not in text:
            violations.append(f"{rel}:missing_request_helper")
        if "issue_runtime_decision" in text:
            violations.append(f"{rel}:direct_gateway_helper_still_present")
        if "executor.execute(" in text:
            violations.append(f"{rel}:direct_executor_execute_still_present")
    assert violations == [], violations


def test_scheduler_orchestrator_surfaces_have_single_path_markers() -> None:
    scheduler = (ROOT / "runtime" / "scheduler.py").read_text(encoding="utf-8")
    run_cycle = (ROOT / "runtime" / "scheduler_run_cycle.py").read_text(encoding="utf-8")
    monitoring_flow = (ROOT / "runtime" / "scheduler_monitoring_flow.py").read_text(encoding="utf-8")
    assert "CANON_RUNTIME_SCHEDULER_SINGLE_DECISION_PATH = True" in scheduler
    assert "CANON_RUNTIME_SCHEDULER_ORCHESTRATOR_ONLY = True" in scheduler
    assert "CANON_RUNTIME_SCHEDULER_RUN_CYCLE_ORCHESTRATOR_ONLY = True" in run_cycle
    assert "CANON_RUNTIME_SCHEDULER_RUN_CYCLE_NO_RAW_DECISION_ISSUE = True" in run_cycle
    assert "CANON_RUNTIME_SCHEDULER_MONITORING_FLOW_SINGLE_PATH = True" in monitoring_flow
    assert "CANON_RUNTIME_SCHEDULER_MONITORING_FLOW_GATEWAY_ONLY = True" in monitoring_flow
