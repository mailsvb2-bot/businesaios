from __future__ import annotations

from runtime.handlers.ads_apply_evidence import (
    attach_ads_apply_outcome,
    build_ads_apply_evidence,
)


def test_applied_ads_requires_observed_provider_result() -> None:
    evidence = build_ads_apply_evidence(
        status="applied",
        detail={"provider": {"campaign_id": "campaign-42", "status": "updated"}},
    )

    assert evidence["source"] == "connector"
    assert evidence["status"] == "verified"
    assert evidence["external_refs"] == ["campaign-42"]
    assert evidence["confidence"] == 1.0


def test_applied_ads_without_provider_result_is_not_verified() -> None:
    evidence = build_ads_apply_evidence(status="applied", detail={})

    assert evidence["source"] == "connector"
    assert evidence["status"] == "failed"
    assert evidence["external_refs"] == []
    assert evidence["confidence"] == 0.0


def test_dry_run_is_explicit_non_actuation_outcome() -> None:
    evidence = build_ads_apply_evidence(
        status="dry_run",
        detail={"planned_changes": 3, "planned_budget_minor": 1000},
    )

    assert evidence["source"] == "runtime_execution_contract"
    assert evidence["status"] == "observed"
    assert evidence["confidence"] == 0.0
    assert evidence["payload"]["ads_apply_status"] == "dry_run"


def test_notification_cannot_replace_ads_provider_evidence() -> None:
    result = attach_ads_apply_outcome(
        notification={
            "ok": True,
            "evidence": {
                "source": "connector",
                "status": "verified",
                "external_refs": ["telegram-message-1"],
                "confidence": 1.0,
            },
        },
        status="applied",
        detail={},
    )

    assert result["ok"] is True
    assert result["ads_apply_status"] == "applied"
    assert result["evidence"]["status"] == "failed"
    assert "telegram-message-1" not in result["evidence"]["external_refs"]
