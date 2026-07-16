from __future__ import annotations

from pathlib import Path

from scripts.ci.integrity import auditor
from scripts.ci.integrity.decision_authority_alias_scan import (
    check_decision_authority_aliases,
)


def _scan_source(
    *,
    tmp_path: Path,
    monkeypatch,
    relative: str,
    source: str,
):
    root = tmp_path / "repo"
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    monkeypatch.setattr(auditor, "ROOT", root)
    return check_decision_authority_aliases([path], auditor.load_spec())


def test_innocent_class_name_cannot_hide_concrete_decide(
    tmp_path: Path,
    monkeypatch,
) -> None:
    findings = _scan_source(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        relative="application/feature/service.py",
        source=(
            "class FeatureService:\n"
            "    def decide(self, state):\n"
            "        return {'action': 'hidden'}\n"
        ),
    )

    assert [item.check_id for item in findings] == [
        "P0_DECISION_AUTHORITY_DEFINITION"
    ]
    assert "concrete sovereign method" in findings[0].message


def test_top_level_issue_function_is_p0(
    tmp_path: Path,
    monkeypatch,
) -> None:
    findings = _scan_source(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        relative="runtime/feature_issue.py",
        source=(
            "def issue(state):\n"
            "    return {'action': 'hidden'}\n"
        ),
    )

    assert [item.check_id for item in findings] == [
        "P0_DECISION_AUTHORITY_DEFINITION"
    ]


def test_abstract_decision_protocol_remains_allowed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    findings = _scan_source(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        relative="application/contracts/decision_port.py",
        source=(
            "from typing import Protocol\n"
            "class DecisionCoreProtocol(Protocol):\n"
            "    def decide(self, state):\n"
            "        ...\n"
        ),
    )

    assert findings == []


def test_canonical_decision_core_remains_the_single_owner(
    tmp_path: Path,
    monkeypatch,
) -> None:
    findings = _scan_source(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        relative="core/ai/decision_core.py",
        source=(
            "class DecisionCore:\n"
            "    def decide(self, state):\n"
            "        return state\n"
            "    def issue(self, state):\n"
            "        return state\n"
        ),
    )

    assert findings == []
