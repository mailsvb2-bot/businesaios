from pathlib import Path

from canon.anti_second_brain_rules import FORBIDDEN_DECISION_CLASS_NAMES
from canon.legacy.architecture_lock_tests import build_lock_config
from canon.legacy.hidden_logic_detector import scan_hidden_logic

ROOT = Path(__file__).resolve().parents[2]


def test_second_brain_names_forbidden():
    assert "SecondDecisionCore" in FORBIDDEN_DECISION_CLASS_NAMES


def test_no_forbidden_class_names_in_production_decision_surfaces():
    findings = scan_hidden_logic(build_lock_config(ROOT))
    forbidden = [
        item
        for item in findings
        if item.symbol in FORBIDDEN_DECISION_CLASS_NAMES
    ]
    assert forbidden == [], (
        "Canonical hidden-logic scanner found a second decision brain:\n"
        + "\n".join(
            f"- {item.relpath}:{item.lineno} [{item.symbol}] {item.reason}"
            for item in forbidden
        )
    )
