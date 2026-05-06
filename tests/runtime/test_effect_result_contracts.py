from __future__ import annotations

from runtime._internal.effect_results import (
    EffectResultStatus,
    canonical_effect_result,
    failure_result,
    result_contract_fields,
    retryable_result,
    success_result,
)
from runtime._internal.effect_types import EffectActionType


def test_result_contract_fields_are_stable() -> None:
    assert result_contract_fields() == (
        "status",
        "action_type",
        "ok",
        "retryable",
        "data",
        "error",
        "external_id",
        "external_refs",
        "verification_status",
        "verification_confidence",
        "cost",
        "evidence",
        "timestamp",
    )


def test_canonical_effect_result_normalizes_legacy_success_payload() -> None:
    result = canonical_effect_result(EffectActionType.CRM_WRITE_RECORD, {"ok": True, "json": {"saved": True}, "external_ref": "crm:1"})
    assert result["status"] == EffectResultStatus.SUCCESS
    assert result["ok"] is True
    assert result["action_type"] == "crm.write_record"
    assert result["data"]["json"] == {"saved": True}
    assert result["external_refs"] == ["crm:1"]
    assert result["verification_status"] == "verified"
    assert result["timestamp"] > 0


def test_result_helpers_keep_canonical_shape() -> None:
    ok = success_result(EffectActionType.ADS_UPDATE_BUDGET, external_id="ad-1", json={"ok": True})
    assert ok["status"] == EffectResultStatus.SUCCESS
    assert ok["external_id"] == "ad-1"

    failed = failure_result(EffectActionType.WEBSITE_PUBLISH_PAGE, error="boom")
    assert failed["status"] == EffectResultStatus.FAILURE
    assert failed["ok"] is False
    assert failed["error"] == "boom"

    retryable = retryable_result(EffectActionType.PAYMENTS_YOOKASSA_CREATE, error="timeout")
    assert retryable["status"] == EffectResultStatus.RETRYABLE
    assert retryable["retryable"] is True
