from __future__ import annotations

from execution.effectors.router import EffectorRouter


def test_effector_evidence_carries_connector_capabilities() -> None:
    router = EffectorRouter()
    result = router.execute(
        action_type="launch_campaign",
        action={
            "action_id": "a-1",
            "channel": "ads",
            "decision_id": "d-1",
            "correlation_id": "c-1",
            "payload": {"budget": 50, "idempotency_key": "idem-123", "dry_run": True},
        },
    )
    assert result.executed is False
    assert result.operator_required is True
    assert "connector_capabilities" in result.evidence
    assert result.evidence["connector_capabilities"]["verify"] is False
    assert result.code in {"dry_run_not_supported", "idempotency_not_supported", "not_configured"}
