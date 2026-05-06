from __future__ import annotations
from pathlib import Path

from runtime.execution.contracts import RuntimeExecutorPort

ROOT = Path(__file__).resolve().parents[2]


def test_runtime_guard_module_has_no_decide_calls() -> None:
    path = ROOT / "runtime" / "guard.py"
    text = path.read_text(encoding="utf-8")
    assert ".issue(" not in text


def test_runtime_executor_contract_surface_is_execution_only() -> None:
    assert hasattr(RuntimeExecutorPort, "execute")
    assert "decide" not in RuntimeExecutorPort.__name__.lower()
