from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_runtime_action_result_presenter_collapse_into_package_alias() -> None:
    text = (ROOT / "runtime/application/__init__.py").read_text(encoding="utf-8")
    assert '"action_result_presenter": "application.decision.action_result_presenter"' in text
    assert not (ROOT / "runtime/application/action_result_presenter.py").exists()


def test_core_package_root_exports_canonical_action_result_presenter() -> None:
    text = (ROOT / "core/decision/__init__.py").read_text(encoding="utf-8")
    assert "present_action_execution_result" in text
    assert "CANON_CORE_DECISION_ACTION_RESULT_PRESENTER" in text or "present_action_execution_result" in text
