from __future__ import annotations

"""Canonical runtime governance public surface."""

from core.governance.builders.audit_record_builder import build_audit_record
from core.governance.contracts import AuditRecord, RestrictionProposal
from core.governance.evaluators.profit_metrics import ProfitMetricsService
from core.governance.explainers.decision_audit_explainer import explain_decision_audit
from core.governance.guards.feedback_loop_guard import FeedbackLoopGuard
from core.governance.guards.policy_update_gate import PolicyUpdateGate, PolicyUpdateGateError
from core.governance.readers import event_sourced_path as _event_sourced_path
from core.governance.repositories.actuation_registry import ActuationRegistry
from core.governance.service import build_restriction_proposal
from core.governance.types import PolicyState

CANON_RUNTIME_GOVERNANCE_PUBLIC_API = True

__all__ = [
    'CANON_RUNTIME_GOVERNANCE_NAMESPACE',
    "ActuationRegistry",
    "AuditRecord",
    "RestrictionProposal",
    "PolicyState",
    "ProfitMetricsService",
    "FeedbackLoopGuard",
    "PolicyUpdateGate",
    "PolicyUpdateGateError",
    "CANON_RUNTIME_GOVERNANCE_PUBLIC_API",
    "assert_governance_event_store_contract",
    "build_audit_record",
    "build_restriction_proposal",
    "explain_decision_audit",
]

CANON_RUNTIME_GOVERNANCE_NAMESPACE = True


def assert_governance_event_store_contract(event_store) -> None:
    return _event_sourced_path.assert_governance_event_store_contract(event_store)



