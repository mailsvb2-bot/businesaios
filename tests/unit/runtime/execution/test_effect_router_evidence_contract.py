from __future__ import annotations

from runtime._internal.effect_evidence_contract import (
    effect_result_to_evidence,
    evidence_contract_fields,
)
from runtime._internal.effect_types import EffectActionType


def test_effect_router_evidence_contract_exposes_explicit_verified_boolean() -> None:
    assert "verified" in evidence_contract_fields()


def test_successful_effect_router_result_is_explicitly_verified() -> None:
    evidence = effect_result_to_evidence(
        EffectActionType.CRM_WRITE_RECORD,
        {
            "ok": True,
            "status": "success",
            "external_id": "crm-record-42",
            "external_refs": ["crm-record-42"],
        },
    )

    assert evidence["source"] == "effect_router"
    assert evidence["verified"] is True
    assert evidence["status"] == "verified"
    assert evidence["confidence"] == 1.0


def test_failed_effect_router_result_is_never_explicitly_verified() -> None:
    evidence = effect_result_to_evidence(
        EffectActionType.WEBSITE_PUBLISH_PAGE,
        {"ok": False, "status": "failure", "error": "provider_failed"},
    )

    assert evidence["verified"] is False
    assert evidence["confidence"] == 0.0


def test_pending_or_retryable_evidence_is_not_promoted_to_verified() -> None:
    evidence = effect_result_to_evidence(
        EffectActionType.ADS_UPDATE_BUDGET,
        {
            "ok": False,
            "status": "retryable",
            "retryable": True,
            "verification_status": "pending",
            "verification_confidence": 0.49,
        },
    )

    assert evidence["verified"] is False
    assert evidence["status"] == "pending"
