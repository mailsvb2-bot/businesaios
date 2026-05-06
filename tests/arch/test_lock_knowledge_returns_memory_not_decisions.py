from __future__ import annotations

from pathlib import Path


def test_knowledge_contract_is_memory_not_decisions() -> None:
    text = Path("core/knowledge/__canon_domain__.py").read_text(encoding="utf-8")
    assert 'CANON_DOMAIN_ROLE = "memory_and_explainability_only"' in text
    assert "CANON_DECISION_ISSUANCE_ALLOWED = False" in text
