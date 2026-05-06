from __future__ import annotations

from core.knowledge import contracts as shim
from core.knowledge.contracts import repositories as repos
from runtime.decision_gateway import DecisionIssuer
from bootstrap.decision_core_contract import RuntimeDecisionCorePort


def test_knowledge_contract_shim_points_to_package_owner() -> None:
    assert shim.LessonRepository is repos.LessonRepository
    assert shim.PatternRepository is repos.PatternRepository


def test_runtime_decision_issuer_uses_boot_contract_owner() -> None:
    assert DecisionIssuer is RuntimeDecisionCorePort
