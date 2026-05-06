from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_runtime_action_result_and_errors_collapse_into_package_aliases() -> None:
    text = (ROOT / "runtime/application/__init__.py").read_text(encoding="utf-8")
    assert '"action_result": "application.decision.action_result"' in text
    assert '"action_errors": "application.decision.action_errors"' in text
    assert not (ROOT / "runtime/application/action_result.py").exists()
    assert not (ROOT / "runtime/application/action_errors.py").exists()


def test_core_package_root_exports_canonical_action_result_and_errors() -> None:
    text = (ROOT / "core/decision/__init__.py").read_text(encoding="utf-8")
    assert "ActionExecutionResult" in text
    assert "DecisionApplicationError" in text
