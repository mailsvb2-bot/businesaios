from __future__ import annotations

from pathlib import Path


def test_business_autonomy_no_parallel_delayed_outcome_writes() -> None:
    root = Path(__file__).resolve().parents[2]
    owner = "runtime/business_autonomy/delayed_outcome_bridge.py"
    facade = "application/business_autonomy/delayed_outcome_bridge.py"
    offenders: list[str] = []

    for path in root.rglob("*.py"):
        rel = path.relative_to(root).as_posix()
        if rel.startswith(("tests/", ".venv/")) or rel in {owner, facade}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if (
            "delayed_outcomes.jsonl" in text
            or "delayed_outcome_quarantine.jsonl" in text
        ):
            offenders.append(rel)

    assert not offenders, f"parallel delayed-outcome paths found: {offenders}"

    owner_text = (root / owner).read_text(encoding="utf-8")
    facade_text = (root / facade).read_text(encoding="utf-8")
    assert "def business_autonomy_delayed_outcome_path(" in owner_text
    assert "def business_autonomy_delayed_outcome_quarantine_path(" in owner_text
    assert (
        "from runtime.business_autonomy import delayed_outcome_bridge as _runtime_bridge"
        in facade_text
    )
    assert "globals().update(" in facade_text
    assert "def business_autonomy_delayed_outcome_path(" not in facade_text
    assert "class BusinessAutonomyDelayedOutcomeBridge" not in facade_text
