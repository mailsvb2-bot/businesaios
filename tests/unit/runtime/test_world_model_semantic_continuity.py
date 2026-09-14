from __future__ import annotations

import pytest

from contracts.event_store import BusinessFactV1
from runtime.state import (
    StateSynthesisEngine,
    StateSynthesisRequest,
    business_fact_to_state_observation,
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


def test_future_replacement_keeps_current_base_value_until_valid_from() -> None:
    engine = StateSynthesisEngine()
    base = engine.synthesize(
        StateSynthesisRequest(
            tenant_id="tenant-1",
            business_id="business-1",
            now_ms=2_000,
            observations=(
                semantic_observation(
                    field_path="business.plan",
                    value="current",
                    source="owner",
                    observed_at_ms=1_900,
                    kind="state",
                    authoritative=True,
                ),
            ),
        )
    )
    future = semantic_observation(
        field_path="business.plan",
        value="next",
        source="owner",
        observed_at_ms=2_100,
        valid_from_ms=3_000,
        kind="state",
        authoritative=True,
    )

    before = engine.synthesize(
        StateSynthesisRequest(
            tenant_id="tenant-1",
            business_id="business-1",
            now_ms=2_500,
            observations=(future,),
            base_snapshot=base,
        )
    )
    assert before.values["business"]["plan"] == "current"
    assert before.fields["business.plan"].value == "current"

    after = engine.synthesize(
        StateSynthesisRequest(
            tenant_id="tenant-1",
            business_id="business-1",
            now_ms=3_100,
            observations=(future,),
            base_snapshot=base,
        )
    )
    assert after.values["business"]["plan"] == "next"
    assert after.fields["business.plan"].value == "next"


def test_human_required_conflict_survives_unrelated_snapshot_rehydration() -> None:
    engine = StateSynthesisEngine()
    conflicted = engine.synthesize(
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
    original_field = conflicted.fields["business.cash"]
    [original_conflict] = conflicted.conflicts

    rehydrated = engine.synthesize(
        StateSynthesisRequest(
            tenant_id="tenant-1",
            business_id="business-1",
            now_ms=2_500,
            observations=(
                semantic_observation(
                    field_path="business.status",
                    value="open",
                    source="crm",
                    observed_at_ms=2_400,
                    kind="state",
                ),
            ),
            base_snapshot=conflicted,
        )
    )
    [carried] = [item for item in rehydrated.conflicts if item.field_path == "business.cash"]
    carried_field = rehydrated.fields["business.cash"]
    assert carried.status == "human_required"
    assert carried.chosen_provenance_hash == original_conflict.chosen_provenance_hash
    assert carried_field.provenance_hash == original_field.provenance_hash
    assert carried_field.value_kind == original_field.value_kind
    assert carried_field.meta["conflict_status"] == "human_required"
    [semantic] = [item for item in rehydrated.semantic_view.records if item.key == "business.cash"]  # type: ignore[union-attr]
    assert semantic.meta["conflict_status"] == "human_required"


def test_business_fact_provenance_survives_durable_and_semantic_projection() -> None:
    provenance = {
        "provider": "billing-ledger",
        "record_id": "provider-row-77",
        "source_records": {"payment": "pay-7", "invoice": "inv-2"},
        "confidence": 0.92,
        "authoritative": True,
    }
    fact = BusinessFactV1(
        fact_id="fact-provenance",
        tenant_id="tenant-1",
        business_id="business-1",
        fact_type="payment.received",
        entity_id="customer-7",
        event_time_ms=1_000,
        observed_at_ms=1_100,
        source="payments",
        payload={"amount": 700},
        provenance=provenance,
    )
    snapshot = StateSynthesisEngine().synthesize(_request(business_fact_to_state_observation(fact)))
    [field] = [item for item in snapshot.fields.values() if item.meta.get("business_fact_id") == fact.fact_id]
    assert field.meta["business_fact_provenance"] == provenance
    [semantic] = snapshot.semantic_view.records_for("fact")  # type: ignore[union-attr]
    assert semantic.meta["observation_meta"]["business_fact_provenance"] == provenance


def test_invalid_future_observation_is_not_materialized_or_projected() -> None:
    future = semantic_observation(
        field_path="business.future_cash",
        value=999,
        source="clock-skewed-source",
        observed_at_ms=200_000,
        kind="fact",
        authoritative=True,
    )
    snapshot = StateSynthesisEngine().synthesize(
        StateSynthesisRequest(
            tenant_id="tenant-1",
            business_id="business-1",
            now_ms=2_000,
            observations=(future,),
        )
    )
    assert snapshot.fields["business.future_cash"].freshness_status == "invalid_future"
    assert snapshot.values == {}
    assert snapshot.semantic_view is not None
    assert snapshot.semantic_view.records == ()


def test_invalid_future_replacement_keeps_current_base_value() -> None:
    engine = StateSynthesisEngine()
    base = engine.synthesize(
        _request(
            semantic_observation(
                field_path="business.cash",
                value=100,
                source="ledger",
                observed_at_ms=1_900,
                kind="fact",
                authoritative=True,
            )
        )
    )
    snapshot = engine.synthesize(
        StateSynthesisRequest(
            tenant_id="tenant-1",
            business_id="business-1",
            now_ms=2_500,
            observations=(
                semantic_observation(
                    field_path="business.cash",
                    value=500,
                    source="clock-skewed-source",
                    observed_at_ms=200_000,
                    kind="fact",
                    authoritative=True,
                ),
            ),
            base_snapshot=base,
        )
    )
    assert snapshot.values["business"]["cash"] == 100
    assert snapshot.fields["business.cash"].value == 100
    assert snapshot.fields["business.cash"].provenance_hash == base.fields["business.cash"].provenance_hash


def test_human_required_conflict_survives_temporally_invalid_same_path_update() -> None:
    engine = StateSynthesisEngine()
    conflicted = engine.synthesize(
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
    snapshot = engine.synthesize(
        StateSynthesisRequest(
            tenant_id="tenant-1",
            business_id="business-1",
            now_ms=2_500,
            observations=(
                semantic_observation(
                    field_path="business.cash",
                    value=130,
                    source="bank:c",
                    observed_at_ms=2_400,
                    valid_from_ms=3_000,
                    kind="fact",
                    authoritative=True,
                ),
            ),
            base_snapshot=conflicted,
        )
    )
    [conflict] = snapshot.conflicts
    assert conflict.status == "human_required"
    assert snapshot.fields["business.cash"].conflict is True
    assert snapshot.fields["business.cash"].meta["conflict_status"] == "human_required"


def test_independent_business_facts_for_same_subject_keep_distinct_identity() -> None:
    facts = tuple(
        BusinessFactV1(
            fact_id=f"payment-fact-{index}",
            tenant_id="tenant-1",
            business_id="business-1",
            fact_type="payment.received",
            entity_id="customer-7",
            event_time_ms=1_000 + index,
            observed_at_ms=1_100 + index,
            source="payments",
            payload={"amount": 100 * index},
        )
        for index in (1, 2)
    )
    snapshot = StateSynthesisEngine().synthesize(
        _request(*(business_fact_to_state_observation(fact) for fact in facts))
    )
    fact_fields = [item for item in snapshot.fields.values() if item.meta.get("business_fact_id")]
    assert len(fact_fields) == 2
    assert {item.meta["business_fact_id"] for item in fact_fields} == {fact.fact_id for fact in facts}
    assert snapshot.semantic_view is not None
    assert len(snapshot.semantic_view.records_for("fact")) == 2


def test_mixed_epistemic_layers_for_same_key_fail_closed() -> None:
    with pytest.raises(ValueError, match="mixed epistemic kinds"):
        StateSynthesisEngine().synthesize(
            _request(
                semantic_observation(
                    field_path="business.cash",
                    value=100,
                    source="ledger",
                    observed_at_ms=1_900,
                    kind="fact",
                ),
                semantic_observation(
                    field_path="business.cash",
                    value=120,
                    source="forecast-model",
                    observed_at_ms=1_900,
                    kind="forecast",
                ),
            )
        )


def test_mixed_epistemic_layers_across_snapshots_fail_closed() -> None:
    engine = StateSynthesisEngine()
    base = engine.synthesize(
        _request(
            semantic_observation(
                field_path="business.cash",
                value=100,
                source="ledger",
                observed_at_ms=1_900,
                kind="fact",
            )
        )
    )
    with pytest.raises(ValueError, match="mixed epistemic kinds"):
        engine.synthesize(
            StateSynthesisRequest(
                tenant_id="tenant-1",
                business_id="business-1",
                now_ms=2_500,
                observations=(
                    semantic_observation(
                        field_path="business.cash",
                        value=120,
                        source="forecast-model",
                        observed_at_ms=2_400,
                        kind="forecast",
                    ),
                ),
                base_snapshot=base,
            )
        )


def test_rehydration_preserves_semantic_record_identity_and_source() -> None:
    engine = StateSynthesisEngine()
    base = engine.synthesize(
        _request(
            semantic_observation(
                field_path="business.cash",
                value=100,
                source="ledger",
                observed_at_ms=1_900,
                kind="fact",
                authoritative=True,
            )
        )
    )
    assert base.semantic_view is not None
    [base_semantic] = base.semantic_view.records

    rehydrated = engine.synthesize(
        StateSynthesisRequest(
            tenant_id="tenant-1",
            business_id="business-1",
            now_ms=2_500,
            observations=(
                semantic_observation(
                    field_path="business.status",
                    value="open",
                    source="crm",
                    observed_at_ms=2_400,
                    kind="state",
                ),
            ),
            base_snapshot=base,
        )
    )
    assert rehydrated.semantic_view is not None
    [carried] = [item for item in rehydrated.semantic_view.records if item.key == "business.cash"]
    assert carried.record_id == base_semantic.record_id
    assert carried.provenance_hash == base_semantic.provenance_hash
    assert carried.source == "ledger"
    assert not carried.source.startswith("snapshot:")


def test_business_fact_supersession_deactivates_referenced_fact() -> None:
    engine = StateSynthesisEngine()
    original = BusinessFactV1(
        fact_id="fact-1",
        tenant_id="tenant-1",
        business_id="business-1",
        fact_type="customer.status",
        entity_id="customer-7",
        event_time_ms=1_000,
        observed_at_ms=1_100,
        source="crm",
        payload={"status": "active"},
    )
    base = engine.synthesize(_request(business_fact_to_state_observation(original)))
    replacement = BusinessFactV1(
        fact_id="fact-2",
        tenant_id="tenant-1",
        business_id="business-1",
        fact_type="customer.status",
        entity_id="customer-7",
        event_time_ms=1_500,
        observed_at_ms=1_600,
        source="crm",
        payload={"status": "inactive"},
        supersedes_fact_id="fact-1",
    )
    updated = engine.synthesize(
        StateSynthesisRequest(
            tenant_id="tenant-1",
            business_id="business-1",
            now_ms=2_000,
            observations=(business_fact_to_state_observation(replacement),),
            base_snapshot=base,
        )
    )
    by_fact_id = {record.meta.get("business_fact_id"): record for record in updated.fields.values()}
    assert by_fact_id["fact-1"].freshness_status == "superseded"
    assert by_fact_id["fact-1"].meta["superseded_by_business_fact_id"] == "fact-2"
    assert by_fact_id["fact-2"].freshness_status not in {"superseded", "expired", "not_yet_valid"}
    assert updated.semantic_view is not None
    assert [record.value["fact_id"] for record in updated.semantic_view.records_for("fact")] == ["fact-2"]
