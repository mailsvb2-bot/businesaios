from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_closed_loop_orchestrator_has_no_long_horizon_import() -> None:
    content = _read("execution/closed_loop_orchestrator.py")
    assert "LongHorizonPlanner" not in content
    assert "goal_decomposition_engine" not in content
    assert "strategy_memory" not in content


def test_headless_flow_has_no_alternative_long_horizon_planning_path() -> None:
    for relative_path in (
        "application/headless/closed_loop.py",
        "execution/headless_contract.py",
        "execution/autonomy_loop.py",
    ):
        content = _read(relative_path)
        assert "LongHorizonPlanner" not in content
        assert "run_long_horizon" not in content
        assert "goal_decomposition_engine" not in content


def test_multi_goal_planner_is_the_only_execution_surface_using_long_horizon_planner() -> None:
    execution_dir = ROOT / "execution"
    owners: list[str] = []
    for path in execution_dir.glob("*.py"):
        content = path.read_text(encoding="utf-8")
        if "LongHorizonPlanner" in content:
            owners.append(path.name)
    assert sorted(owners) == ["headless_boot.py", "long_horizon_planner.py", "multi_goal_planner.py"]
