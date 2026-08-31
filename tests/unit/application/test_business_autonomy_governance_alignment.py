import pytest

from core.human_governance.policy import HumanGovernancePolicy
from interfaces.api.business_autonomy_route_handlers import build_business_autonomy_route_handlers


def test_business_autonomy_governance_alignment_preview() -> None:
    handlers = build_business_autonomy_route_handlers()
    alignment = handlers.get_governance_alignment("sample_business")
    assert alignment["business_id"] == "sample_business"
    assert "execution_verdict" in alignment
    assert "normalized_request" in alignment
    assert "approval" in alignment["execution_verdict"]


def test_sales_handoff_is_governance_evidence_only() -> None:
    policy = HumanGovernancePolicy()
    signal = policy.evaluate_sales_handoff(tenant_id="tenant-a", subject_id="lead-1", model_confidence=0.99, sensitive_context=True, subject_closed=True)
    assert signal is not None and signal["reason"] == "sensitive_context" and signal["risk_level"] == "critical"
    assert signal["decision_authority"] is False and signal["effect_authority"] is False
    assert policy.evaluate_sales_handoff(tenant_id="tenant-a", subject_id="lead-2", model_confidence=0.1, subject_closed=True) is None
    with pytest.raises(ValueError, match="model_confidence"):
        policy.evaluate_sales_handoff(tenant_id="tenant-a", subject_id="lead-3", model_confidence=float("nan"))
