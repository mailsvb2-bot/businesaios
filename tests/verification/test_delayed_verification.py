from datetime import UTC, datetime
from runtime._internal.effect_types import EffectActionType

from execution.verification.verification_engine import VerificationEngine, execution_receipt_evidence, router_evidence


def test_delayed_verification_retries_until_external_evidence_arrives() -> None:
    engine = VerificationEngine()
    started_at = datetime(2026, 3, 23, 12, 0, 0, tzinfo=UTC)
    action = {
        "action_id": "act-3",
        "action_type": EffectActionType.CRM_WRITE_RECORD.value,
        "external_confirmation_mode": "required",
        "verification_timeout_seconds": 600,
        "verification_retry_backoff_seconds": [30, 60, 120],
    }
    first = engine.verify(
        action=action,
        evidence=[
            execution_receipt_evidence(
                action_id="act-3",
                action_type=EffectActionType.CRM_WRITE_RECORD.value,
                ok=True,
                status="observed",
            ),
            router_evidence(
                action_id="act-3",
                action_type=EffectActionType.CRM_WRITE_RECORD.value,
                verified=False,
                status="pending",
                external_refs=["crm:lead:123"],
                confidence=0.2,
            ),
        ],
        now=started_at,
        attempt_index=0,
    ).to_dict()
    assert first["decision"]["verified"] is False
    assert first["decision"]["status"] == "pending"
    assert first["decision"]["delayed"] is True
    assert first["retry_plan"]["should_retry"] is True
    assert first["retry_plan"]["next_attempt_index"] == 1

    second = engine.verify(
        action=action,
        evidence=[
            execution_receipt_evidence(
                action_id="act-3",
                action_type=EffectActionType.CRM_WRITE_RECORD.value,
                ok=True,
                status="observed",
            ),
            router_evidence(
                action_id="act-3",
                action_type=EffectActionType.CRM_WRITE_RECORD.value,
                verified=True,
                status="verified",
                external_refs=["crm:lead:123"],
                confidence=1.0,
            ),
        ],
        now=datetime(2026, 3, 23, 12, 1, 0, tzinfo=UTC),
        attempt_index=1,
    ).to_dict()
    assert second["decision"]["verified"] is True
    assert second["decision"]["status"] == "verified"
    assert second["retry_plan"]["should_retry"] is False
