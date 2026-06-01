from __future__ import annotations

from runtime._internal.effect_evidence_contract import effect_result_to_evidence, evidence_contract_fields
from runtime._internal.effect_types import EffectActionType


def test_effect_result_to_evidence_keeps_canonical_shape() -> None:
    evidence = effect_result_to_evidence(
        EffectActionType.PAYMENTS_YOOKASSA_GET_STATUS,
        {"ok": True, "status": "success", "external_ref": "pay:1", "verification_confidence": 0.8},
    )
    assert evidence_contract_fields() == (
        "source",
        "action_type",
        "status",
        "summary",
        "external_refs",
        "confidence",
        "payload",
    )
    assert evidence["source"] == "effect_router"
    assert evidence["action_type"] == "payments.yookassa.get_status"
    assert evidence["status"] == "verified"
    assert evidence["external_refs"] == ["pay:1"]
    assert evidence["confidence"] == 0.8
