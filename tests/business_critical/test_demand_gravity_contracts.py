from __future__ import annotations

from datetime import datetime, timezone

import pytest

from runtime.demand_gravity import DemandChannel, DemandSignal, DemandSignalCandidateProducer, DemandSignalKind, build_demand_gravity_admin_view
from runtime.demand_gravity.no_second_brain import DemandGravitySecondBrainViolation, assert_payload_has_no_decision_fields


def _signal() -> DemandSignal:
    return DemandSignal(
        signal_id="sig-1",
        tenant_id="tenant-a",
        kind=DemandSignalKind.SEARCH_INTENT,
        channel=DemandChannel.GOOGLE_MAPS,
        observed_at=datetime.now(timezone.utc),
        source_ref="source:1",
        normalized_text="coffee near me",
        confidence=0.8,
        raw_fingerprint="fp-1",
    )


def test_demand_gravity_produces_only_advisory_decision_core_candidates() -> None:
    candidate = DemandSignalCandidateProducer().build_candidates(tenant_id="tenant-a", signals=(_signal(),))[0]

    assert candidate.write_mode.value == "advisory_only"
    assert candidate.payload["execution_allowed"] is False
    assert candidate.payload["decision_owner"] == "DecisionCore"
    assert candidate.evidence_refs == ("source:1",)
    assert candidate.idempotency_key.startswith("demand-gravity:dgc_")


def test_demand_gravity_blocks_nested_decision_payloads() -> None:
    with pytest.raises(DemandGravitySecondBrainViolation):
        assert_payload_has_no_decision_fields({"outer": {"execute_now": True}})


def test_demand_gravity_admin_surface_is_json_safe() -> None:
    candidate = DemandSignalCandidateProducer().build_candidates(tenant_id="tenant-a", signals=(_signal(),))[0]
    view = build_demand_gravity_admin_view(tenant_id="tenant-a", candidates=(candidate,))

    assert view["surface"] == "demand_gravity"
    assert view["hard_guards"]["can_execute"] is False
    assert isinstance(view["candidates"][0]["created_at"], str)
