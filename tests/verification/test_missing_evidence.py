from execution.verification.verification_engine import VerificationEngine, execution_receipt_evidence
from runtime._internal.effect_types import EffectActionType


def test_missing_external_evidence_blocks_verification() -> None:
    engine = VerificationEngine()
    action = {
        "action_id": "act-1",
        "action_type": EffectActionType.TELEGRAM_SEND_MESSAGE.value,
        "external_confirmation_mode": "required",
    }
    result = engine.verify(
        action=action,
        evidence=[
            execution_receipt_evidence(
                action_id="act-1",
                action_type=EffectActionType.TELEGRAM_SEND_MESSAGE.value,
                ok=True,
                status="observed",
            )
        ],
    ).to_dict()
    assert result["decision"]["verified"] is False
    assert result["decision"]["status"] == "missing_evidence"
    assert result["decision"]["code"] == "missing_external_evidence"
    assert result["decision"]["retryable"] is True
    assert result["decision"]["source_of_truth"] in {"executor", "none"}
