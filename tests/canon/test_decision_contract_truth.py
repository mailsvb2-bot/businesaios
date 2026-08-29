from __future__ import annotations

from contracts.decisioning import Decision as ExportedDecision
from contracts.decisioning import DecisionEnvelope as ExportedDecisionEnvelope
from contracts.decisioning.sovereign_decision_contract import Decision, DecisionEnvelope
from core.ai.decision_contracts import Decision as CoreDecision
from core.ai.decision_contracts import DecisionEnvelope as CoreDecisionEnvelope


def test_sovereign_decision_has_one_semantic_owner() -> None:
    assert CoreDecision is Decision
    assert ExportedDecision is Decision
    assert Decision.__module__ == "contracts.decisioning.sovereign_decision_contract"


def test_sovereign_decision_envelope_has_one_semantic_owner() -> None:
    assert CoreDecisionEnvelope is DecisionEnvelope
    assert ExportedDecisionEnvelope is DecisionEnvelope
    assert DecisionEnvelope.__module__ == "contracts.decisioning.sovereign_decision_contract"
