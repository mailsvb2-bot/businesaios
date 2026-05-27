from __future__ import annotations

from pathlib import Path

FORBIDDEN = [
    "issue_decision(",
    "emit_action(",
    "apply_action(",
    "dispatch_action(",
    "execute_action(",
    "decisioncore",
    "select_strategy(",
]


def test_knowledge_service_never_issues_actions() -> None:
    text = Path("core/knowledge/service.py").read_text(encoding="utf-8").lower()
    for token in FORBIDDEN:
        assert token not in text, token
