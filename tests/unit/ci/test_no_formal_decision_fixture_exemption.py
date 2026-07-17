from __future__ import annotations

from pathlib import Path

from scripts.ci.integrity import auditor
from scripts.ci.integrity.decision_authority_alias_scan import (
    check_decision_authority_aliases,
)


def _scan(path: Path) -> list[auditor.Finding]:
    return check_decision_authority_aliases([path], auditor.load_spec())


def test_former_snapshot_decision_core_shape_is_now_p0(
    tmp_path: Path,
    monkeypatch,
) -> None:
    root = tmp_path / "repo"
    path = root / "formal/regression_gate/project_snapshot_bundle.py"
    path.parent.mkdir(parents=True)
    path.write_text(
        "class _SelectingDecisionCore:\n"
        "    CANON_NON_RUNTIME_REGRESSION_FIXTURE = True\n"
        "    def evaluate(self, state):\n"
        "        return state\n"
        "    decide = evaluate\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(auditor, "ROOT", root)

    findings = _scan(path)

    assert [item.check_id for item in findings] == [
        "P0_DECISION_AUTHORITY_DEFINITION"
    ]


def test_current_snapshot_bundle_needs_no_decision_authority_exemption() -> None:
    findings = _scan(
        Path("formal/regression_gate/project_snapshot_bundle.py")
    )

    assert findings == []
