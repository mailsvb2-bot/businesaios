"""Telegram action producers cannot bypass signed single-action execution."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _proposed_actions(path: str) -> set[str]:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    actions = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "propose" and node.args:
            if isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                actions.add(node.args[0].value)
    return actions


def test_autopilot_launch_never_issues_unsigned_composite_plan():
    actions = _proposed_actions("core/policies/telegram/handlers/autopilot_parts/flow_launch.py")
    assert "execute_plan@v1" not in actions
    assert "set_user_setting@v1" in actions


def test_profit_sprint_callbacks_never_issue_unsigned_composite_plan():
    actions = _proposed_actions("core/policies/telegram/handlers/autopilot_parts/flow.py")
    assert "execute_plan@v1" not in actions
    assert "profit_sprint_onboarding_start@v1" in actions
    assert "profit_sprint_onboarding_lead_source@v1" in actions


def test_production_guard_still_rejects_non_noop_inline_plan():
    from runtime.enforcement.action_contracts import validate_execute_plan_payload
    import pytest

    with pytest.raises(RuntimeError, match="EXECUTE_PLAN_STEP_REQUIRES_SEPARATE_DECISION_ENVELOPE"):
        validate_execute_plan_payload(
            action="execute_plan@v1",
            payload={"steps": [{"action": "send_message@v1", "action_schema_version": 1}]},
            schemas=object(),
        )
