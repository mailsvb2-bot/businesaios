from __future__ import annotations

import json

import pytest

from contracts.event_store import BusinessFactV1
from runtime.state import (
    STATE_SYNTHESIS_SCHEMA_VERSION,
    StateSynthesisEngine,
    StateSynthesisRequest,
    business_fact_to_state_observation,
    migrate_legacy_snapshot_from_dict,
    semantic_observation,
    snapshot_from_dict,
)


def _request(*observations, now_ms: int = 2_000, base_snapshot=None) -> StateSynthesisRequest:
    return StateSynthesisRequest(
        tenant_id="tenant-1",
        business_id="business-1",
        now_ms=now_ms,
        observations=tuple(observations),
        base_snapshot=base_snapshot,
    )


def _simple_snapshot():
    return StateSynthesisEngine().synthesize(
        _request(
            semantic_observation(
                field_path="business.cash",
                value=100,
                source="ledger",
                observed_at_ms=1_500,
                kind="fact",
                authoritative=True,
            )
        )
    )


def _json_payload(snapshot) -> dict:
    return json.loads(json.dumps(snapshot.to_dict()))


def _fact(
    fact_id: str,
    *,
    supersedes_fact_id: str | None = None,
    event_time_ms: int,
    observed_at_ms: int,
) -> BusinessFactV1:
    return BusinessFactV1(
        fact_id=fact_id,
        tenant_id="tenant-1",
        business_id="business-1",
        fact_type="customer.status",
        entity_id="customer-7",
        event_time_ms=event_time_ms,
        observed_at_ms=observed_at_ms,
        source="crm",
        payload={"status": fact_id},
        supersedes_fact_id=supersedes_fact_id,
    )


def test_current_snapshot_missing_provenance_envelope_fails_closed() -> None:
    payload = _json_payload(_simple_snapshot())
    assert payload["schema_version"] == STATE_SYNTHESIS_SCHEMA_VERSION == "state_synthesis@v2"
    [field_path] = payload["fields"]
    payload["fields"][field_path].pop("provenance_envelope")

    with pytest.raises(ValueError, match="current state snapshot is missing provenance envelope"):
        snapshot_from_dict(payload)


def test_downgrade_label_does_not_enable_implicit_legacy_migration() -> None:
    payload = _json_payload(_simple_snapshot())
    [field_path] = payload["fields"]
    payload["fields"][field_path].pop("provenance_envelope")
    payload["schema_version"] = "state_synthesis@v1"

    with pytest.raises(ValueError, match="requires explicit trusted migration"):
        snapshot_from_dict(payload)


def test_explicit_legacy_migration_rekeys_old_snapshot() -> None:
    payload = _json_payload(_simple_snapshot())
    [field_path] = payload["fields"]
    old_hash = payload["fields"][field_path]["provenance_hash"]
    payload["fields"][field_path].pop("provenance_envelope")
    payload["schema_version"] = "state_synthesis@v1"

    migrated = migrate_legacy_snapshot_from_dict(payload)
    record = migrated.fields[field_path]
    assert migrated.schema_version == "state_synthesis@v2"
    assert record.provenance_envelope
    assert record.provenance_hash != old_hash
    assert record.meta["legacy_provenance_rekeyed_from"] == old_hash


def test_snapshot_field_map_key_must_match_protected_record_path() -> None:
    payload = _json_payload(_simple_snapshot())
    [field_path] = payload["fields"]
    record = payload["fields"].pop(field_path)
    payload["fields"]["business.debt"] = record

    with pytest.raises(ValueError, match="state field map key mismatch"):
        snapshot_from_dict(payload)


def test_value_kind_is_bound_to_provenance_envelope() -> None:
    payload = _json_payload(_simple_snapshot())
    [field_path] = payload["fields"]
    payload["fields"][field_path]["value_kind"] = "unknown"

    with pytest.raises(ValueError, match="provenance envelope mismatch for unknown"):
        snapshot_from_dict(payload)


def _conflicted_snapshot():
    return StateSynthesisEngine().synthesize(
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


def test_current_conflict_missing_id_cannot_authorize_tampered_candidate() -> None:
    payload = _json_payload(_conflicted_snapshot())
    conflict = payload["conflicts"][0]
    conflict["candidate_provenance_hashes"][0] = "f" * 64
    conflict.pop("conflict_id")

    with pytest.raises(ValueError, match="current state conflict_id is required"):
        snapshot_from_dict(payload)


def test_current_conflict_candidate_tamper_rejects_stale_id() -> None:
    payload = _json_payload(_conflicted_snapshot())
    payload["conflicts"][0]["candidate_provenance_hashes"][0] = "f" * 64

    with pytest.raises(ValueError, match="current state conflict candidate hashes are invalid"):
        snapshot_from_dict(payload)


def test_persisted_semantic_view_is_rebuilt_from_validated_fields() -> None:
    payload = _json_payload(_simple_snapshot())
    payload["semantic_view"]["records"][0]["value"] = 999_999

    restored = snapshot_from_dict(payload)
    assert restored.semantic_view is not None
    [record] = restored.semantic_view.records
    assert record.key == "business.cash"
    assert record.value == 100
    assert record.provenance_hash == restored.fields["business.cash"].provenance_hash


def test_corrected_successor_reactivates_previously_superseded_target() -> None:
    engine = StateSynthesisEngine()
    target = business_fact_to_state_observation(
        _fact("fact-target", event_time_ms=1_000, observed_at_ms=1_100)
    )
    successor = business_fact_to_state_observation(
        _fact(
            "fact-successor",
            supersedes_fact_id="fact-target",
            event_time_ms=1_500,
            observed_at_ms=1_600,
        )
    )
    superseded = engine.synthesize(_request(target, successor, now_ms=2_000))
    by_id = {record.meta.get("business_fact_id"): record for record in superseded.fields.values()}
    assert by_id["fact-target"].freshness_status == "superseded"
    assert by_id["fact-target"].meta["superseded_by_business_fact_id"] == "fact-successor"

    corrected_successor = business_fact_to_state_observation(
        _fact(
            "fact-successor",
            supersedes_fact_id=None,
            event_time_ms=2_100,
            observed_at_ms=2_200,
        )
    )
    rehydrated_superseded = snapshot_from_dict(_json_payload(superseded))
    corrected = engine.synthesize(
        _request(corrected_successor, now_ms=2_500, base_snapshot=rehydrated_superseded)
    )
    by_id = {record.meta.get("business_fact_id"): record for record in corrected.fields.values()}
    restored = by_id["fact-target"]
    assert restored.freshness_status != "superseded"
    assert restored.value_kind == "known"
    assert restored.superseded_at_ms is None
    assert "superseded_by_business_fact_id" not in restored.meta
    assert corrected.semantic_view is not None
    assert {record.value["fact_id"] for record in corrected.semantic_view.records_for("fact")} == {
        "fact-target",
        "fact-successor",
    }


def test_current_snapshot_recomputes_freshness_from_protected_temporal_envelope() -> None:
    snapshot = StateSynthesisEngine().synthesize(
        _request(
            semantic_observation(
                field_path="business.expiring_offer",
                value={"active": True},
                source="catalog",
                observed_at_ms=1_000,
                valid_until_ms=1_500,
                ttl_ms=10_000,
                kind="fact",
                authoritative=True,
            ),
            now_ms=2_000,
        )
    )
    payload = _json_payload(snapshot)
    field = payload["fields"]["business.expiring_offer"]
    assert field["freshness_status"] == "expired"
    field["freshness_status"] = "fresh"
    field["freshness_reason"] = "tampered"

    restored = snapshot_from_dict(payload)
    record = restored.fields["business.expiring_offer"]
    assert record.freshness_status == "expired"
    assert record.freshness_reason == "after_valid_until"
    assert restored.semantic_view is not None
    assert restored.semantic_view.records == ()


def test_current_snapshot_rejects_conflict_status_tamper_without_resolution_envelope() -> None:
    payload = _json_payload(_conflicted_snapshot())
    payload["conflicts"][0]["status"] = "resolved"

    with pytest.raises(ValueError, match="resolved conflict field mismatch"):
        snapshot_from_dict(payload)
