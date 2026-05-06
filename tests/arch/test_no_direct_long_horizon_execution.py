from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


FORBIDDEN_IMPORT_TARGETS = (
    "execution.long_horizon_planner",
    "execution.goal_decomposition_engine",
    "execution.strategy_memory",
)

FORBIDDEN_RUNTIME_TOKENS = (
    "LongHorizonPlanner",
    "GoalDecompositionEngine",
    "StrategyMemoryService",
    "long_horizon",
    "remaining_action_hints",
    "checkpoint_task_ids",
    "parallelizable_task_ids",
)


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_execution_runtime_surfaces_do_not_import_long_horizon_stack() -> None:
    guarded_paths = (
        "execution/closed_loop_orchestrator.py",
        "application/headless/closed_loop.py",
        "execution/headless_contract.py",
        "application/headless/feedback.py",
        "application/headless/step_builder.py",
        "execution/autonomy_loop.py",
        "runtime/executor.py",
        "runtime/executor_runtime_support.py",
    )
    for relative_path in guarded_paths:
        content = _read(relative_path)
        for target in FORBIDDEN_IMPORT_TARGETS:
            assert target not in content, f"{relative_path} must not import {target}"



def test_runtime_and_orchestration_surfaces_do_not_execute_from_long_horizon_metadata() -> None:
    guarded_paths = (
        "execution/closed_loop_orchestrator.py",
        "application/headless/closed_loop.py",
        "execution/headless_contract.py",
        "application/headless/feedback.py",
        "application/headless/step_builder.py",
        "runtime/executor.py",
        "runtime/executor_runtime_support.py",
        "runtime/execution/dispatcher.py",
        "runtime/queue/job_dispatcher.py",
    )
    for relative_path in guarded_paths:
        content = _read(relative_path)
        for token in FORBIDDEN_RUNTIME_TOKENS:
            assert token not in content, f"{relative_path} must not route execution from {token}"



def test_only_planning_surfaces_may_reference_long_horizon_metadata() -> None:
    allowed = {
        "execution/headless_boot.py",
        "execution/long_horizon_planner.py",
        "execution/multi_goal_planner.py",
        "execution/performance_feedback_learning.py",
        "execution/goal_decomposition_engine.py",
        "execution/strategy_memory.py",
        "application/planning/long_horizon_planner.py",
        "application/planning/multi_goal_planner.py",
        "application/planning/strategy_memory.py",
    }
    offenders: list[str] = []
    for path in ROOT.rglob("*.py"):
        try:
            relative = str(path.relative_to(ROOT))
        except ValueError:
            continue
        if "/tests/" in f"/{relative}":
            continue
        content = path.read_text(encoding="utf-8")
        if "long_horizon" in content and relative not in allowed:
            offenders.append(relative)
    assert offenders == [], f"Unexpected long_horizon references outside planning surfaces: {sorted(offenders)}"
