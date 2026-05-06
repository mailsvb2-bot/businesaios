from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "runtime" / "handlers" / "ads_autopilot_flow.py"


def test_ads_autopilot_flow_is_thin() -> None:
    if not TARGET.exists():
        return

    tree = ast.parse(TARGET.read_text(encoding="utf-8"))

    banned_calls = {
        "launch",
        "execute_campaign",
        "apply_budget",
        "rebalance",
        "mutate_policy",
    }

    offenders: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name in banned_calls:
                offenders.append(func_name)

    assert not offenders, (
        "ads_autopilot_flow must remain thin and may not perform implicit side effects. "
        f"Offending calls: {sorted(set(offenders))}"
    )
