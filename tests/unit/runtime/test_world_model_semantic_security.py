from __future__ import annotations

import hashlib
import json

import pytest

from contracts.event_store import BusinessFactV1
from runtime.state import (
    FileStateDeltaLog,
    StateConflictResolution,
    StateEvidenceRef,
    StateSynthesisEngine,
    StateSynthesisRequest,
    business_fact_to_state_observation,
    semantic_observation,
    snapshot_from_dict,
)


def _fact(
    fact_id: str,
    *,
    fact_type: str = "customer.status_changed",
    entity_id: str = "customer-1",
    supersedes_fact_id: str | None = None,
    event_time_ms: int = 1_000,
    observed_at_ms: int = 1_100,
    provenance: dict | None = None,
    source: str = "crm",
) -> BusinessFactV1:
    return BusinessFactV1(
        fact_id=fact_id,
        tenant_id="tenant-1",
        business_id="business-1",
        fact_type=fact_type,
        entity_id=entity_id,
        event_time_ms=event_time_ms,
        observed_at_ms=observed_at_ms,
        source=source,
        payload={"fact": fact_id},
        provenance=provenance,
        supersedes_fact_id=supersedes_fact_id,
    )


def _request(*observations, now_ms: int = 2_000, base_snapshot=None) -> StateSynthesisRequest:
    return StateSynthesisRequest(
        tenant_id="tenant-1",
        business_id="business-1",
        now_ms=now_ms,
        observations=tuple(observations),
        base_snapshot=base_snapshot,
    )


def test_business_fact_path_components_are_hashed_before_materialization() -> None:
    first = _fact("fact-1")
    first_hash = hashlib.sha256(first.fact_id.encode("utf-8")).hexdigest()
    attacker = _fact(
        "fact-2",
        fact_type=f"{first.fact_type}.{first.entity_id}.by_id.{first_hash}.nested",
        entity_id="entity.with.separators",
        event_time_ms=1_010,
        observed_at_ms=1_110,
    )
    observations = tuple(business_fact_to_state_observation(fact) for fact in (first, attacker))
    assert first.fact_type not in observations[0].field_path
    assert first.entity_id not in observations[0].field_path
    assert attacker.fact_type not in observations[1].field_path
    assert attacker.entity_id not in observations[1].field_path

    snapshot = StateSynthesisEngine().synthesize(_request(*observations))
    by_id = {record.meta.get("business_fact_id"): record for record in snapshot.fields.values()}
    assert set(by_id) == {"fact-1", "fact-2"}
    assert by_id["fact-1"].value == {
        "fact_id": "fact-1",
        "tenant_id": "tenant-1",
        "business_id": "business-1",
        "fact_type": "customer.status_changed",
        "entity_id": "customer-1",
        "event_time_ms": 1_000,
        "payload": {"fact": "fact-1"},
        "supersedes_fact_id": None,
    }


def test_generic_state_observation_cannot_forge_business_fact_supersession() -> None:
    base = StateSynthesisEngine().synthesize(_request(business_fact_to_state_observation(_fact("fact-1"))))
    forged = semantic_observation(
        field_path="business.forged",
        value={"supersedes_fact_id": "fact-1"},
        source="caller",
        observed_at_ms=1_900,
        kind="state",
        meta={"business_fact_id": "forged"},
    )
    with pytest.raises(ValueError, match="business_fact metadata is reserved"):
        _request(forged, now_ms=2_500, base_snapshot=base)


def test_generic_supersedes_payload_without_trusted_business_fact_marker_has_no_effect() -> None:
    engine = StateSynthesisEngine()
    base = engine.synthesize(_request(business_fact_to_state_observation(_fact("fact-1"))))
    generic = semantic_observation(
        field_path="business.note",
        value={"supersedes_fact_id": "fact-1"},
        source="caller",
        observed_at_ms=2_400,
        kind="state",
    )
    updated = engine.synthesize(_request(generic, now_ms=2_500, base_snapshot=base))
    [fact_record] = [item for item in updated.fields.values() if item.meta.get("business_fact_id") == "fact-1"]
    assert fact_record.freshness_status != "superseded"


def test_conflict_resolution_rejects_base_candidate_that_expired_after_conflict() -> None:
    engine = StateSynthesisEngine()
    conflicted = engine.synthesize(
        _request(
            semantic_observation(
                field_path="business.cash",
                value=100,
                source="bank:a",
                observed_at_ms=1_500,
                valid_from_ms=1_000,
                valid_until_ms=2_100,
                kind="fact",
                authoritative=True,
            ),
            semantic_observation(
                field_path="business.cash",
                value=120,
                source="bank:b",
                observed_at_ms=1_400,
                valid_from_ms=1_000,
                valid_until_ms=2_100,
                kind="fact",
                authoritative=True,
            ),
        )
    )
    [conflict] = conflicted.conflicts
    resolution = StateConflictResolution(
        field_path="business.cash",
        conflict_id=conflict.conflict_id,
        selected_provenance_hash=conflict.chosen_provenance_hash,
        resolved_by="operator:finance-owner",
        resolved_at_ms=2_450,
        evidence_refs=(StateEvidenceRef(evidence_id="resolution-expired", kind="human_resolution"),),
    )
    with pytest.raises(ValueError, match="selected base conflict candidate is not decision-eligible"):
        engine.synthesize(
            StateSynthesisRequest(
                tenant_id="tenant-1",
                business_id="business-1",
                now_ms=2_500,
                observations=(),
                base_snapshot=conflicted,
                conflict_resolutions=(resolution,),
            )
        )


def test_business_fact_supersession_lifecycle_is_explicit_in_delta_log(tmp_path) -> None:
    delta_path = tmp_path / "state-delta.jsonl"
    engine = StateSynthesisEngine(delta_log=FileStateDeltaLog(delta_path))
    base = engine.synthesize(_request(business_fact_to_state_observation(_fact("fact-1"))))
    replacement = _fact(
        "fact-2",
        supersedes_fact_id="fact-1",
        event_time_ms=2_200,
        observed_at_ms=2_300,
    )
    updated = engine.synthesize(
        _request(business_fact_to_state_observation(replacement), now_ms=2_500, base_snapshot=base)
    )
    target_path = next(
        path for path, record in updated.fields.items() if record.meta.get("business_fact_id") == "fact-1"
    )
    rows = [json.loads(line) for line in delta_path.read_text(encoding="utf-8").splitlines()]
    target_delta = next(item for item in rows[-1]["deltas"] if item["field_path"] == target_path)
    assert target_delta["change_kind"] == "updated"
    assert target_delta["change_reason"] == "lifecycle"
    assert target_delta["previous_provenance_hash"] == target_delta["current_provenance_hash"]
    assert target_delta["previous_lifecycle"]["freshness_status"] == "fresh"
    assert target_delta["current_lifecycle"]["freshness_status"] == "superseded"
    assert target_delta["current_lifecycle"]["superseded_by_business_fact_id"] == "fact-2"


def test_cyclic_business_fact_supersession_fails_closed() -> None:
    fact_a = _fact("fact-a", supersedes_fact_id="fact-b", event_time_ms=1_000, observed_at_ms=1_100)
    fact_b = _fact("fact-b", supersedes_fact_id="fact-a", event_time_ms=1_010, observed_at_ms=1_110)
    with pytest.raises(ValueError, match="cyclic BusinessFact supersession"):
        StateSynthesisEngine().synthesize(
            _request(
                business_fact_to_state_observation(fact_a),
                business_fact_to_state_observation(fact_b),
            )
        )



def test_rehydrated_base_does_not_rotate_unresolved_conflict_identity() -> None:
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
    [before] = conflicted.conflicts
    carried = engine.synthesize(_request(now_ms=2_100, base_snapshot=conflicted))
    [after] = carried.conflicts
    assert after.conflict_id == before.conflict_id
    assert after.candidate_provenance_hashes == before.candidate_provenance_hashes
    assert after.candidate_sources == before.candidate_sources


def test_business_fact_supersession_rejects_post_request_payload_mutation() -> None:
    engine = StateSynthesisEngine()
    base = engine.synthesize(_request(business_fact_to_state_observation(_fact("fact-1"))))
    projected = business_fact_to_state_observation(_fact("fact-2"))
    request = _request(projected, now_ms=2_500, base_snapshot=base)
    projected.value["supersedes_fact_id"] = "fact-1"
    with pytest.raises(ValueError, match="trusted BusinessFact supersession mismatch"):
        engine.synthesize(request)


def test_scheduled_business_fact_supersession_uses_validity_boundary() -> None:
    engine = StateSynthesisEngine()
    target = _fact(
        "fact-1",
        event_time_ms=1_500,
        observed_at_ms=1_550,
        provenance={"valid_from_ms": 1_500},
    )
    base = engine.synthesize(_request(business_fact_to_state_observation(target), now_ms=1_600))
    replacement = _fact(
        "fact-2",
        supersedes_fact_id="fact-1",
        event_time_ms=1_000,
        observed_at_ms=1_700,
        provenance={"valid_from_ms": 2_000},
    )
    scheduled = engine.synthesize(
        _request(business_fact_to_state_observation(replacement), now_ms=1_900, base_snapshot=base)
    )
    by_id = {record.meta.get("business_fact_id"): record for record in scheduled.fields.values()}
    assert by_id["fact-1"].freshness_status != "superseded"
    assert by_id["fact-2"].freshness_status == "not_yet_valid"

    activated = engine.synthesize(_request(now_ms=2_100, base_snapshot=scheduled))
    by_id = {record.meta.get("business_fact_id"): record for record in activated.fields.values()}
    assert by_id["fact-1"].freshness_status == "superseded"
    assert by_id["fact-1"].superseded_at_ms == 2_000
    assert by_id["fact-1"].meta["superseded_by_business_fact_id"] == "fact-2"


def test_unscoped_observation_provenance_is_bound_to_request_scope() -> None:
    observation = semantic_observation(
        field_path="business.cash",
        value=100,
        source="ledger",
        observed_at_ms=1_500,
        kind="fact",
    )
    engine = StateSynthesisEngine()
    first = engine.synthesize(
        StateSynthesisRequest(
            tenant_id="tenant-a",
            business_id="business-a",
            now_ms=2_000,
            observations=(observation,),
        )
    )
    second = engine.synthesize(
        StateSynthesisRequest(
            tenant_id="tenant-b",
            business_id="business-b",
            now_ms=2_000,
            observations=(observation,),
        )
    )
    first_field = first.fields["business.cash"]
    second_field = second.fields["business.cash"]
    assert first_field.provenance_hash != second_field.provenance_hash
    assert first.semantic_view is not None
    assert second.semantic_view is not None
    assert first.semantic_view.records[0].record_id != second.semantic_view.records[0].record_id


def test_conflicted_business_fact_successor_cannot_apply_supersession() -> None:
    target = business_fact_to_state_observation(_fact("fact-target"))
    superseding = business_fact_to_state_observation(
        _fact(
            "fact-successor",
            supersedes_fact_id="fact-target",
            source="crm:a",
            provenance={"authoritative": True},
        )
    )
    nonsuperseding = business_fact_to_state_observation(
        _fact(
            "fact-successor",
            supersedes_fact_id=None,
            source="crm:b",
            provenance={"authoritative": True},
        )
    )
    snapshot = StateSynthesisEngine().synthesize(_request(target, superseding, nonsuperseding))
    by_id = {record.meta.get("business_fact_id"): record for record in snapshot.fields.values()}
    assert by_id["fact-successor"].conflict is True
    assert by_id["fact-successor"].meta["conflict_status"] == "human_required"
    assert by_id["fact-target"].freshness_status != "superseded"
    assert "superseded_by_business_fact_id" not in by_id["fact-target"].meta


def test_snapshot_rejects_tampered_value_with_retained_provenance_hash() -> None:
    snapshot = StateSynthesisEngine().synthesize(
        _request(business_fact_to_state_observation(_fact("fact-1")))
    )
    payload = json.loads(json.dumps(snapshot.to_dict()))
    [field_path] = payload["fields"]
    payload["fields"][field_path]["value"]["payload"]["fact"] = "tampered"
    with pytest.raises(ValueError, match="provenance envelope mismatch for value"):
        snapshot_from_dict(payload)


def test_resolved_conflict_history_survives_unrelated_synthesis() -> None:
    engine = StateSynthesisEngine()
    bank_a = semantic_observation(
        field_path="business.cash",
        value=100,
        source="bank:a",
        observed_at_ms=1_500,
        kind="fact",
        authoritative=True,
    )
    bank_b = semantic_observation(
        field_path="business.cash",
        value=120,
        source="bank:b",
        observed_at_ms=1_400,
        kind="fact",
        authoritative=True,
    )
    conflicted = engine.synthesize(_request(bank_a, bank_b))
    [conflict] = conflicted.conflicts
    resolution = StateConflictResolution(
        field_path="business.cash",
        conflict_id=conflict.conflict_id,
        selected_provenance_hash=conflict.chosen_provenance_hash,
        resolved_by="operator:finance-owner",
        resolved_at_ms=2_100,
        evidence_refs=(
            StateEvidenceRef(
                evidence_id="resolution-history-proof",
                kind="human_resolution",
                observed_at_ms=2_100,
            ),
        ),
    )
    resolved = engine.synthesize(
        StateSynthesisRequest(
            tenant_id="tenant-1",
            business_id="business-1",
            now_ms=2_200,
            observations=(),
            base_snapshot=conflicted,
            conflict_resolutions=(resolution,),
        )
    )
    [resolved_conflict] = [item for item in resolved.conflicts if item.status == "resolved"]
    carried = engine.synthesize(
        _request(
            semantic_observation(
                field_path="business.note",
                value="unrelated",
                source="operator",
                observed_at_ms=2_300,
                kind="state",
            ),
            now_ms=2_400,
            base_snapshot=resolved,
        )
    )
    [history] = [item for item in carried.conflicts if item.status == "resolved"]
    assert history.conflict_id == resolved_conflict.conflict_id
    assert history.candidate_provenance_hashes == resolved_conflict.candidate_provenance_hashes
    assert history.resolution_policy == "human_evidence_bound_resolution@v1"
    assert history.resolution_evidence_refs == resolved_conflict.resolution_evidence_refs
