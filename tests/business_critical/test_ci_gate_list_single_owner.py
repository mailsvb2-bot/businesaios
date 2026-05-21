from __future__ import annotations

from scripts.ci.cli import build_parser
from scripts.ci.plan_registry import allowed_gates, plan_for_gate


def test_cli_gate_choices_are_owned_by_plan_registry() -> None:
    parser = build_parser()
    gate_action = next(action for action in parser._actions if "--gate" in action.option_strings)

    assert tuple(gate_action.choices) == allowed_gates()
    for gate in allowed_gates():
        assert plan_for_gate(gate).gate == gate


def test_cli_source_does_not_redeclare_gate_names() -> None:
    text = __import__("pathlib").Path("scripts/ci/cli.py").read_text(encoding="utf-8")

    assert "choices=allowed_gates()" in text
    assert "postgres-live" not in text
    assert "business-critical" not in text
    assert "production-boot" not in text
