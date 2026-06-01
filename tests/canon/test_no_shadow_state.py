from __future__ import annotations

from pathlib import Path

from canon.legacy.architecture_lock_tests import build_lock_config
from canon.legacy.data_flow_validator import scan_shadow_state, verify_single_state_source_files_exist

ROOT = Path(__file__).resolve().parents[2]


def test_no_shadow_state_markers() -> None:
    config = build_lock_config(ROOT)
    findings = scan_shadow_state(config)
    critical = [item for item in findings if item.severity.value == "critical"]
    assert critical == [], (
        "Shadow-state / parallel-world-state identifiers detected:\n"
        + "\n".join(f"- {item.relpath}:{item.lineno} [{item.symbol}] {item.reason}" for item in critical[:50])
    )


def test_required_canonical_state_surfaces_exist() -> None:
    config = build_lock_config(ROOT)
    findings = verify_single_state_source_files_exist(config)
    assert findings == (), (
        "Canonical state surfaces are missing:\n"
        + "\n".join(f"- {item.relpath}: {item.reason}" for item in findings)
    )
