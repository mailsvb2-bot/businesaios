from __future__ import annotations

from datetime import UTC, datetime

import pytest

from runtime.demand_gravity import (
    DemandChannel,
    DemandSignal,
    DemandSignalCandidateProducer,
    DemandSignalKind,
    build_demand_gravity_admin_view,
)
from runtime.demand_gravity.no_second_brain import (
    DemandGravitySecondBrainViolation,
    assert_payload_has_no_decision_fields,
)


def _signal(*, raw: dict[str, object] | None = None, business_id: str = "biz-a") -> DemandSignal:
    return DemandSignal(
        signal_id="sig-1",
        tenant_id="tenant-a",
        business_id=business_id,
        kind=DemandSignalKind.SEARCH_INTENT,
        channel=DemandChannel.GOOGLE_MAPS,
        observed_at=datetime.now(UTC),
        source_ref="source:1",
        normalized_text="coffee near me",
        confidence=0.8,
        raw_fingerprint="fp-1",
        raw=raw or {},
    )


def test_demand_gravity_produces_only_business_scoped_advisory_candidates() -> None:
    candidate = DemandSignalCandidateProducer().build_candidates(tenant_id="tenant-a", business_id="biz-a", signals=(_signal(),))[0]

    assert candidate.write_mode.value == "advisory_only"
    assert candidate.tenant_id == "tenant-a"
    assert candidate.business_id == "biz-a"
    assert candidate.payload["execution_allowed"] is False
    assert candidate.payload["decision_owner"] == "DecisionCore"
    assert candidate.payload["business_id"] == "biz-a"
    assert candidate.evidence_refs == ("source:1",)
    assert candidate.idempotency_key.startswith("demand-gravity:tenant-a:biz-a:dgc_")


def test_demand_gravity_rejects_cross_business_signals() -> None:
    with pytest.raises(ValueError, match="cross_business_signal_forbidden"):
        DemandSignalCandidateProducer().build_candidates(tenant_id="tenant-a", business_id="biz-a", signals=(_signal(business_id="biz-b"),))


def test_demand_gravity_blocks_nested_decision_payloads_in_candidate_and_raw_signal() -> None:
    with pytest.raises(DemandGravitySecondBrainViolation):
        assert_payload_has_no_decision_fields({"outer": {"execute_now": True}})
    with pytest.raises(DemandGravitySecondBrainViolation):
        DemandSignalCandidateProducer().build_candidates(
            tenant_id="tenant-a",
            business_id="biz-a",
            signals=(_signal(raw={"outer": {"ranked_channels": ["maps"]}}),),
        )


def test_demand_gravity_admin_surface_is_json_safe() -> None:
    candidate = DemandSignalCandidateProducer().build_candidates(tenant_id="tenant-a", business_id="biz-a", signals=(_signal(),))[0]
    view = build_demand_gravity_admin_view(tenant_id="tenant-a", candidates=(candidate,))

    assert view["surface"] == "demand_gravity"
    assert view["business_ids"] == ["biz-a"]
    assert view["hard_guards"]["can_execute"] is False
    assert view["hard_guards"]["requires_business_scope"] is True
    assert isinstance(view["candidates"][0]["created_at"], str)
