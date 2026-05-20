from __future__ import annotations

from datetime import datetime, timezone

import pytest

from runtime.demand_gravity import (
    DemandChannel,
    DemandGravityDecisionCoreBridge,
    DemandSignal,
    DemandSignalCandidateProducer,
    DemandSignalKind,
    build_demand_gravity_admin_view,
)
from runtime.demand_gravity.no_second_brain import DemandGravitySecondBrainViolation, assert_payload_has_no_decision_fields


def _signal(*, signal_id: str = "sig-1", tenant_id: str = "tenant-a", fingerprint: str = "fp-1") -> DemandSignal:
    return DemandSignal(
        signal_id=signal_id,
        tenant_id=tenant_id,
        kind=DemandSignalKind.SEARCH_INTENT,
        channel=DemandChannel.GOOGLE_MAPS,
        observed_at=datetime.now(timezone.utc),
        source_ref=f"source:{signal_id}",
        normalized_text="coffee near me",
        confidence=0.9,
        raw_fingerprint=fingerprint,
    )


def test_candidate_producer_builds_advisory_only_candidate() -> None:
    now = datetime.now(timezone.utc)
    candidates = DemandSignalCandidateProducer().build_candidates(
        tenant_id="tenant-a",
        signals=(_signal(),),
        now=now,
        correlation_id="corr-1",
    )

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.candidate_id.startswith("dgc_")
    assert candidate.tenant_id == "tenant-a"
    assert candidate.payload["execution_allowed"] is False
    assert candidate.payload["decision_owner"] == "DecisionCore"
    assert candidate.idempotency_key == f"demand-gravity:{candidate.candidate_id}"
    assert candidate.correlation_id == "corr-1"


def test_candidate_producer_rejects_cross_tenant_signal() -> None:
    with pytest.raises(ValueError, match="cross_tenant_signal_forbidden"):
        DemandSignalCandidateProducer().build_candidates(
            tenant_id="tenant-a",
            signals=(_signal(tenant_id="tenant-b"),),
        )


def test_candidate_producer_deduplicates_fingerprints() -> None:
    candidates = DemandSignalCandidateProducer().build_candidates(
        tenant_id="tenant-a",
        signals=(
            _signal(signal_id="sig-1", fingerprint="same"),
            _signal(signal_id="sig-2", fingerprint="same"),
        ),
    )

    assert len(candidates) == 1
    assert candidates[0].signal_ids == ("sig-1",)


def test_payload_decision_fields_are_blocked_recursively() -> None:
    with pytest.raises(DemandGravitySecondBrainViolation, match="winner_channel"):
        assert_payload_has_no_decision_fields({"nested": {"winner_channel": "search_ads"}})


class FakeDecisionCore:
    def ingest_demand_candidate(self, candidate) -> str:
        return f"decision:{candidate.candidate_id}"


def test_bridge_submits_only_valid_candidates_to_decision_port() -> None:
    candidate = DemandSignalCandidateProducer().build_candidates(
        tenant_id="tenant-a",
        signals=(_signal(),),
    )[0]

    refs = DemandGravityDecisionCoreBridge(FakeDecisionCore()).submit_candidates((candidate,))

    assert refs == (f"decision:{candidate.candidate_id}",)


def test_admin_view_is_json_safe_and_explicit_about_ownership() -> None:
    candidate = DemandSignalCandidateProducer().build_candidates(
        tenant_id="tenant-a",
        signals=(_signal(),),
    )[0]

    view = build_demand_gravity_admin_view(tenant_id="tenant-a", candidates=(candidate,), decision_refs=("decision:1",))

    assert view["surface"] == "demand_gravity"
    assert view["decision_owner"] == "DecisionCore"
    assert view["hard_guards"]["can_execute"] is False
    assert isinstance(view["candidates"][0]["created_at"], str)
    assert view["candidates"][0]["channel"] == "google_maps"
