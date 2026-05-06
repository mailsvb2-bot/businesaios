from runtime._internal.effect_types import EffectActionType
from execution.verification.verification_engine import VerificationEngine, connector_snapshot_evidence, execution_receipt_evidence


def test_conflicting_authoritative_evidence_is_terminal() -> None:
    engine = VerificationEngine()
    action = {
        "action_id": "act-2",
        "action_type": EffectActionType.WEBSITE_PUBLISH_PAGE.value,
        "external_confirmation_mode": "required",
        "conflict_is_terminal": True,
    }
    result = engine.verify(
        action=action,
        evidence=[
            execution_receipt_evidence(
                action_id="act-2",
                action_type=EffectActionType.WEBSITE_PUBLISH_PAGE.value,
                ok=True,
                status="observed",
            ),
            connector_snapshot_evidence(
                action_id="act-2",
                action_type=EffectActionType.WEBSITE_PUBLISH_PAGE.value,
                verified=True,
                source="website",
                external_refs=["page:/landing"],
                confidence=1.0,
            ),
            connector_snapshot_evidence(
                action_id="act-2",
                action_type=EffectActionType.WEBSITE_PUBLISH_PAGE.value,
                verified=False,
                source="cdn_probe",
                external_refs=["page:/landing"],
                confidence=0.0,
            ),
        ],
    ).to_dict()
    assert result["decision"]["verified"] is False
    assert result["decision"]["status"] == "conflicting"
    assert result["decision"]["code"] == "conflicting_evidence"
    assert len(result["decision"]["conflicting_evidence_ids"]) == 2
    assert result["decision"]["retryable"] is False
