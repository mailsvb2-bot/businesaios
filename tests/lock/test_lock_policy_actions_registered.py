from __future__ import annotations

import ast
import re
from pathlib import Path

from core.actions.allowed_actions import ALLOWED_ACTIONS

_VERSIONED_TOKEN = re.compile(r"^[A-Za-z0-9_:\-]+@v\d+$")
_ACTION_KEYWORDS = frozenset({"action", "action_type"})


def _literal_action_tokens(tree: ast.AST) -> set[str]:
    """Return only versioned literals used in an action-bearing AST position.

    Policy IDs, event names, schema versions and telemetry vocabulary are not
    executable actions and therefore must not be interpreted as registry
    references merely because they contain ``@vN``.
    """

    tokens: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg in _ACTION_KEYWORDS:
            value = node.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                token = value.value.strip()
                if _VERSIONED_TOKEN.fullmatch(token):
                    tokens.add(token)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if not (
                isinstance(value, ast.Constant)
                and isinstance(value.value, str)
                and _VERSIONED_TOKEN.fullmatch(value.value.strip())
            ):
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id.startswith("ACTION_"):
                    tokens.add(value.value.strip())
    return tokens


def test_policies_do_not_reference_unknown_actions() -> None:
    root = Path(__file__).resolve().parents[2]
    policy_dir = root / "core" / "policies"
    if not policy_dir.exists():
        return

    unknown: set[str] = set()
    for py in policy_dir.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"), filename=str(py))
        unknown.update(_literal_action_tokens(tree).difference(ALLOWED_ACTIONS))

    assert not unknown, f"Unknown action tokens referenced in policies: {sorted(unknown)}"


def test_policy_action_scanner_ignores_policy_and_event_vocabulary() -> None:
    tree = ast.parse(
        'policy_id = "demand_route@v1"\n'
        'event_type = "autopilot_menu_opened@v1"\n'
        'result = ProposedAction(action="route_lead@v1", payload={})\n'
    )
    assert _literal_action_tokens(tree) == {"route_lead@v1"}
