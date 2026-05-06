from __future__ import annotations

from pathlib import Path

from canon.legacy.architecture_lock_tests import assert_no_critical_legacy_findings, build_lock_config
from canon.legacy.hidden_logic_detector import scan_hidden_logic
from canon.legacy.legacy_wrapper_guard import scan_legacy_wrappers


ROOT = Path(__file__).resolve().parents[2]


def test_no_second_decision_path() -> None:
    assert_no_critical_legacy_findings(ROOT)


def test_no_hidden_final_action_shapers_outside_canonical_surfaces() -> None:
    config = build_lock_config(ROOT)
    findings = scan_hidden_logic(config)
    critical = [item for item in findings if item.severity.value == "critical"]
    assert critical == [], (
        "Hidden second-decision path detected outside canonical decision surfaces:\n"
        + "\n".join(f"- {item.relpath}:{item.lineno} [{item.symbol}] {item.reason}" for item in critical[:50])
    )


def test_legacy_wrappers_remain_thin() -> None:
    config = build_lock_config(ROOT)
    findings = scan_legacy_wrappers(config)
    critical = [item for item in findings if item.severity.value == "critical"]
    assert critical == [], (
        "Legacy wrappers became thick and started acting as compatibility brains:\n"
        + "\n".join(f"- {item.relpath}:{item.lineno} [{item.symbol}] {item.reason}" for item in critical[:50])
    )
