from __future__ import annotations

from pathlib import Path

import pytest

from contracts.event_store import BusinessFactV1
from contracts.world_model_semantics import WORLD_MODEL_SEMANTIC_KINDS
from kernel.world_state import WorldStateV1
from runtime.state import (
    FileStateSnapshotStore,
    StateEvidenceRef,
    StateSynthesisEngine,
    StateSynthesisRequest,
    business_fact_to_state_observation,
    migrate_legacy_snapshot_from_dict,
    semantic_observation,
)


def _request(*observations):
    return StateSynthesisRequest(
        tenant_id="tenant-1",
        business_id="business-1",
        now_ms=2_000,
        observations=tuple(observations),
        correlation_id="corr-1",
    )


def test_semantic_layers_match_canon_and_do_not_collapse_epistemic_types() -> None:
    items = [
        ("fact", 1000, True),
        ("state", "stable", False),
        ("belief", 0.3, False),
        ("assumption", "seasonality", False),
        ("goal", "grow", True),
        ("constraint", "budget", True),
        ("opportunity", "upsell", False),
        ("risk", "churn", False),
        ("hypothesis", "faster reply improves conversion", False),
        ("forecast", 1200, False),
        ("preference", "no cold calls", True),
        ("recommendation", "increase follow-up", False),
        ("unknown", None, False),
    ]
    observations = [
        semantic_observation(
            field_path=f"business.semantic.{kind}",
            value=value,
            source=f"source:{kind}",
            observed_at_ms=1_000 + index,
            kind=kind,
            authoritative=authoritative,
            confidence=1.0 if authoritative else 0.7,
        )
        for index, (kind, value, authoritative) in enumerate(items)
    ]
    snapshot = StateSynthesisEngine().synthesize(_request(*observations))
    assert snapshot.semantic_view is not None
    assert tuple(snapshot.semantic_view.as_dict()["layers"]) == WORLD_MODEL_SEMANTIC_KINDS
    assert WORLD_MODEL_SEMANTIC_KINDS == (
        "fact",
        "state",
        "belief",
        "assumption",
        "goal",
        "constraint",
        "opportunity",
        "risk",
        "hypothesis",
        "forecast",
        "preference",
        "recommendation",
        "unknown",
    )
    for kind, _, _ in items:
        [record] = snapshot.semantic_view.records_for(kind)
        assert record.epistemic_type == kind


def test_unknown_first_does_not_turn_missing_knowledge_into_false_zero_or_empty() -> None:
    snapshot = StateSynthesisEngine().synthesize(
        _request(
            semantic_observation(
                field_path="business.unknown.margin",
                value="unknown",
                source="import",
                observed_at_ms=1_500,
                kind="unknown",
            )
        )
    )
    field = snapshot.fields["business.unknown.margin"]
    assert field.value is None
    assert field.value_kind == "unknown"
    [record] = snapshot.semantic_view.records_for("unknown")  # type: ignore[union-attr]
    assert record.value is None
    assert record.epistemic_type == "unknown"


def test_semantic_projection_preserves_temporal_lineage_confidence_freshness_and_evidence() -> None:
    evidence = StateEvidenceRef(evidence_id="ev-1", kind="ledger", uri="ledger://payment/1", observed_at_ms=1_450)
    snapshot = StateSynthesisEngine().synthesize(
        _request(
            semantic_observation(
                field_path="business.payment",
                value=42,
                source="ledger",
                observed_at_ms=1_500,
                recorded_at_ms=1_550,
                occurred_at_ms=1_400,
                valid_from_ms=1_400,
                valid_until_ms=9_000,
                kind="fact",
                confidence=0.75,
                authoritative=True,
                ttl_ms=2_000,
                evidence_refs=(evidence,),
            )
        )
    )
    [record] = snapshot.semantic_view.records  # type: ignore[union-attr]
    assert record.source == "ledger"
    assert record.occurred_at_ms == 1_400
    assert record.observed_at_ms == 1_500
    assert record.recorded_at_ms == 1_550
    assert record.valid_from_ms == 1_400
    assert record.valid_until_ms == 9_000
    assert record.fresh_until_ms == 3_500
    assert record.confidence == 0.75
    assert record.authoritative is True
    assert record.evidence_refs == ("ev-1",)
    assert len(record.provenance_hash) == 64
    assert record.meta["freshness_status"] == "fresh"


def test_business_fact_enters_same_state_synthesis_with_event_time_separate_from_observation_time() -> None:
    fact = BusinessFactV1(
        fact_id="fact-1",
        tenant_id="tenant-1",
        business_id="business-1",
        fact_type="payment.received",
        entity_id="customer-1",
        event_time_ms=1_000,
        observed_at_ms=1_100,
        source="payments",
        payload={"amount": 12000},
        provenance={
            "confidence": 0.9,
            "authoritative": True,
            "ttl_ms": 50_000,
            "recorded_at_ms": 1_200,
            "valid_from_ms": 1_000,
            "valid_until_ms": 8_000,
        },
        decision_id="decision-1",
        correlation_id="corr-1",
    )
    observation = business_fact_to_state_observation(fact)
    assert observation.semantic_kind == "fact"
    assert observation.occurred_at_ms == 1_000
    assert observation.observed_at_ms == 1_100
    assert observation.recorded_at_ms == 1_200
    snapshot = StateSynthesisEngine().synthesize(_request(observation))
    [record] = snapshot.semantic_view.records_for("fact")  # type: ignore[union-attr]
    assert record.value["fact_id"] == "fact-1"
    assert record.value["payload"]["amount"] == 12000
    assert record.occurred_at_ms == 1_000
    assert record.valid_until_ms == 8_000


def test_conflicting_state_is_explicitly_auto_resolved_not_silently_overwritten() -> None:
    snapshot = StateSynthesisEngine().synthesize(
        _request(
            semantic_observation(
                field_path="business.balance",
                value=100,
                source="bank:a",
                observed_at_ms=1_500,
                kind="fact",
                authoritative=True,
            ),
            semantic_observation(
                field_path="business.balance",
                value=90,
                source="import:b",
                observed_at_ms=1_600,
                kind="fact",
                confidence=0.8,
            ),
        )
    )
    assert len(snapshot.conflicts) == 1
    [conflict] = snapshot.conflicts
    assert conflict.status == "auto_resolved"
    assert conflict.resolution_policy == "ranked_state_conflict_policy@v1"
    assert set(conflict.candidate_sources) == {"bank:a", "import:b"}
    assert snapshot.fields["business.balance"].conflict is True


def test_snapshot_round_trip_preserves_semantic_and_conflict_truth(tmp_path: Path) -> None:
    store = FileStateSnapshotStore(tmp_path)
    engine = StateSynthesisEngine(snapshot_store=store)
    original = engine.synthesize(
        _request(
            semantic_observation(
                field_path="business.risk",
                value="low",
                source="risk:a",
                observed_at_ms=1_500,
                kind="risk",
                confidence=0.8,
            ),
            semantic_observation(
                field_path="business.risk",
                value="high",
                source="risk:b",
                observed_at_ms=1_400,
                kind="risk",
                confidence=0.5,
            ),
        )
    )
    loaded = store.load_latest(tenant_id="tenant-1", business_id="business-1")
    assert loaded is not None and loaded.semantic_view is not None and original.semantic_view is not None
    assert loaded.semantic_view.as_dict() == original.semantic_view.as_dict()
    assert loaded.fields["business.risk"].semantic_kind == "risk"
    assert loaded.conflicts[0].status == original.conflicts[0].status
    assert loaded.conflicts[0].resolution_policy == original.conflicts[0].resolution_policy


def test_legacy_snapshot_without_semantic_or_temporal_fields_remains_readable() -> None:
    payload = {
        "state_id": "legacy-state",
        "tenant_id": "tenant-1",
        "business_id": "business-1",
        "synthesized_at_ms": 1_000,
        "schema_version": "state_synthesis@v1",
        "values": {"world": {"signal": 7}},
        "fields": {
            "world.signal": {
                "field_path": "world.signal",
                "value": 7,
                "value_kind": "known",
                "source": "legacy",
                "observed_at_ms": 900,
                "recorded_at_ms": 950,
                "freshness_status": "fresh",
                "freshness_reason": "within_ttl",
                "confidence": 0.8,
                "source_priority": 50,
                "authoritative": False,
                "provenance_hash": "a" * 64,
                "evidence_refs": [],
                "candidates_considered": 1,
                "conflict": False,
                "meta": {},
            }
        },
        "conflicts": [],
        "source_watermarks": {"legacy": 900},
        "audit": {},
        "meta": {},
    }

    snapshot = migrate_legacy_snapshot_from_dict(payload)
    field = snapshot.fields["world.signal"]
    assert snapshot.semantic_view is None
    assert field.semantic_kind == "state"
    assert field.occurred_at_ms is None
    assert field.valid_from_ms is None
    assert field.valid_until_ms is None
    assert field.superseded_at_ms is None


def test_authoritative_conflict_is_visible_in_semantic_view_as_human_required() -> None:
    snapshot = StateSynthesisEngine().synthesize(
        _request(
            semantic_observation(
                field_path="business.cash",
                value=100,
                source="bank:a",
                observed_at_ms=1_500,
                kind="fact",
                authoritative=True,
            ),
            semantic_observation(
                field_path="business.cash",
                value=120,
                source="bank:b",
                observed_at_ms=1_400,
                kind="fact",
                authoritative=True,
            ),
        )
    )
    [conflict] = snapshot.conflicts
    [record] = snapshot.semantic_view.records_for("fact")  # type: ignore[union-attr]
    assert conflict.status == "human_required"
    assert record.meta["conflict"] is True
    assert record.meta["conflict_status"] == "human_required"
    assert record.meta["resolution_policy"] == "authoritative_conflict_requires_human@v1"


def test_sovereign_world_state_serialization_uses_same_semantic_view_not_a_second_state() -> None:
    snapshot = StateSynthesisEngine().synthesize(
        _request(
            semantic_observation(
                field_path="business.constraint",
                value="budget",
                source="owner",
                observed_at_ms=1_500,
                kind="constraint",
                authoritative=True,
            )
        )
    )
    state = WorldStateV1(
        schema_version=1,
        user={},
        session={},
        product={},
        economy={},
        timestamp_ms=2_000,
        tenant_id="tenant-1",
        world_model_semantics=snapshot.semantic_view,
    )
    payload = state.canonical_bytes()
    assert b"world_model_semantics@v1" in payload
    assert b"constraint" in payload


def test_invalid_semantic_kind_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported world-model semantic kind"):
        semantic_observation(field_path="business.x", value=1, source="x", observed_at_ms=1, kind="fabricated_fact")


def test_business_fact_scope_is_preserved_and_cross_scope_requests_fail_closed() -> None:
    fact = BusinessFactV1(
        fact_id="fact-scope",
        tenant_id="tenant-1",
        business_id="business-1",
        fact_type="customer.updated",
        entity_id="customer-7",
        event_time_ms=1_000,
        observed_at_ms=1_100,
        source="crm",
    )
    observation = business_fact_to_state_observation(fact)
    assert observation.tenant_id == "tenant-1"
    assert observation.business_id == "business-1"
    assert observation.value["tenant_id"] == "tenant-1"
    assert observation.value["business_id"] == "business-1"

    for tenant_id, business_id, error in (
        ("tenant-2", "business-1", "observation tenant_id mismatch"),
        ("tenant-1", "business-2", "observation business_id mismatch"),
    ):
        with pytest.raises(ValueError, match=error):
            StateSynthesisRequest(
                tenant_id=tenant_id,
                business_id=business_id,
                now_ms=2_000,
                observations=(observation,),
            )


@pytest.mark.parametrize(
    ("temporal_kwargs", "expected_status"),
    [
        ({"valid_from_ms": 2_500, "valid_until_ms": 3_000}, "not_yet_valid"),
        ({"valid_from_ms": 1_000, "valid_until_ms": 1_500}, "expired"),
        ({"valid_from_ms": 1_000, "superseded_at_ms": 1_500}, "superseded"),
    ],
)
def test_temporally_invalid_facts_remain_auditable_but_do_not_reach_decision_projection(
    temporal_kwargs: dict[str, int], expected_status: str
) -> None:
    snapshot = StateSynthesisEngine().synthesize(
        _request(
            semantic_observation(
                field_path="business.temporal.fact",
                value={"amount": 42},
                source="ledger",
                observed_at_ms=1_000,
                kind="fact",
                authoritative=True,
                ttl_ms=10_000,
                **temporal_kwargs,
            )
        )
    )
    assert snapshot.fields["business.temporal.fact"].freshness_status == expected_status
    assert snapshot.values == {}
    assert snapshot.semantic_view is not None
    assert snapshot.semantic_view.records_for("fact") == ()


def test_semantic_fresh_until_is_capped_by_business_validity() -> None:
    snapshot = StateSynthesisEngine().synthesize(
        _request(
            semantic_observation(
                field_path="business.temporal.active",
                value=7,
                source="ledger",
                observed_at_ms=1_000,
                kind="fact",
                ttl_ms=10_000,
                valid_from_ms=900,
                valid_until_ms=2_500,
            )
        )
    )
    [record] = snapshot.semantic_view.records_for("fact")  # type: ignore[union-attr]
    assert record.fresh_until_ms == 2_500


def test_equivalent_authoritative_mappings_do_not_create_false_conflict() -> None:
    snapshot = StateSynthesisEngine().synthesize(
        _request(
            semantic_observation(
                field_path="business.profile",
                value={"a": 1, "b": 2},
                source="source:a",
                observed_at_ms=1_500,
                kind="state",
                authoritative=True,
            ),
            semantic_observation(
                field_path="business.profile",
                value={"b": 2, "a": 1},
                source="source:b",
                observed_at_ms=1_400,
                kind="state",
                authoritative=True,
            ),
        )
    )
    assert snapshot.conflicts == ()
    assert snapshot.fields["business.profile"].conflict is False


def test_expired_authoritative_observation_does_not_outrank_current_value() -> None:
    snapshot = StateSynthesisEngine().synthesize(
        _request(
            semantic_observation(
                field_path="finance.cash",
                value=100,
                source="old-ledger",
                observed_at_ms=1_400,
                kind="fact",
                authoritative=True,
                valid_from_ms=1_000,
                valid_until_ms=1_500,
            ),
            semantic_observation(
                field_path="finance.cash",
                value=90,
                source="current-feed",
                observed_at_ms=1_600,
                kind="fact",
            ),
        )
    )
    assert snapshot.fields["finance.cash"].value == 90
    assert snapshot.fields["finance.cash"].source == "current-feed"
    assert snapshot.conflicts == ()
