from __future__ import annotations

import pytest

from runtime.state import (
    StateConflictResolution,
    StateEvidenceRef,
    StateSynthesisEngine,
    StateSynthesisRequest,
    migrate_legacy_snapshot_from_dict,
    semantic_observation,
    snapshot_from_dict,
)


def _request(*observations):
    return StateSynthesisRequest(
        tenant_id="tenant-1",
        business_id="business-1",
        now_ms=2_000,
        observations=tuple(observations),
        correlation_id="corr-human-resolution",
    )


def test_human_required_conflict_stays_sticky_on_fresh_same_path_update_without_resolution() -> None:
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
    original = conflicted.fields["business.cash"]
    [original_conflict] = conflicted.conflicts

    updated = engine.synthesize(
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
                    kind="fact",
                    authoritative=True,
                ),
            ),
            base_snapshot=conflicted,
        )
    )

    [carried] = updated.conflicts
    assert carried.conflict_id != original_conflict.conflict_id
    assert carried.status == "human_required"
    assert set(carried.candidate_sources) == {"bank:a", "bank:b", "bank:c"}
    assert len(carried.candidate_provenance_hashes) == 3
    assert updated.fields["business.cash"].provenance_hash == original.provenance_hash
    assert updated.fields["business.cash"].value == original.value
    assert updated.fields["business.cash"].conflict is True
    assert updated.fields["business.cash"].meta["conflict_id"] == carried.conflict_id


def test_human_required_conflict_can_be_resolved_only_to_original_candidate_with_evidence() -> None:
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
    provenance_by_source = dict(zip(conflict.candidate_sources, conflict.candidate_provenance_hashes, strict=True))

    resolution = StateConflictResolution(
        field_path="business.cash",
        conflict_id=conflict.conflict_id,
        selected_provenance_hash=provenance_by_source["bank:b"],
        resolved_by="operator:finance-owner",
        resolved_at_ms=2_450,
        evidence_refs=(
            StateEvidenceRef(
                evidence_id="resolution-ticket-17",
                kind="human_resolution",
                observed_at_ms=2_450,
            ),
        ),
        reason="bank:b reconciled against signed statement",
    )
    resolved = engine.synthesize(
        StateSynthesisRequest(
            tenant_id="tenant-1",
            business_id="business-1",
            now_ms=2_500,
            observations=(bank_b,),
            base_snapshot=conflicted,
            conflict_resolutions=(resolution,),
        )
    )

    [resolved_conflict] = resolved.conflicts
    field = resolved.fields["business.cash"]
    assert resolved_conflict.conflict_id == conflict.conflict_id
    assert resolved_conflict.status == "resolved"
    assert resolved_conflict.resolution_policy == "human_evidence_bound_resolution@v1"
    assert resolved_conflict.resolution_evidence_refs == ("resolution-ticket-17",)
    assert field.value == 120
    assert field.conflict is False
    assert field.meta["conflict_status"] == "resolved"
    assert field.meta["resolved_conflict_id"] == conflict.conflict_id
    assert field.meta["resolved_by"] == "operator:finance-owner"
    assert resolved.values["business"]["cash"] == 120


def test_human_conflict_resolution_rejects_stale_conflict_id_and_non_candidate_selection() -> None:
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
    [conflict] = conflicted.conflicts
    evidence = (StateEvidenceRef(evidence_id="resolution-ticket-18", kind="human_resolution"),)

    with pytest.raises(ValueError, match="conflict_id mismatch"):
        engine.synthesize(
            StateSynthesisRequest(
                tenant_id="tenant-1",
                business_id="business-1",
                now_ms=2_500,
                observations=(),
                base_snapshot=conflicted,
                conflict_resolutions=(
                    StateConflictResolution(
                        field_path="business.cash",
                        conflict_id="stale-conflict-id",
                        selected_provenance_hash=conflict.chosen_provenance_hash,
                        resolved_by="operator:finance-owner",
                        resolved_at_ms=2_450,
                        evidence_refs=evidence,
                    ),
                ),
            )
        )

    with pytest.raises(ValueError, match="not a candidate"):
        engine.synthesize(
            StateSynthesisRequest(
                tenant_id="tenant-1",
                business_id="business-1",
                now_ms=2_500,
                observations=(),
                base_snapshot=conflicted,
                conflict_resolutions=(
                    StateConflictResolution(
                        field_path="business.cash",
                        conflict_id=conflict.conflict_id,
                        selected_provenance_hash="not-a-conflict-candidate",
                        resolved_by="operator:finance-owner",
                        resolved_at_ms=2_450,
                        evidence_refs=evidence,
                    ),
                ),
            )
        )


def test_conflict_identity_and_candidate_provenance_survive_snapshot_roundtrip() -> None:
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
    restored = snapshot_from_dict(snapshot.to_dict())
    [before] = snapshot.conflicts
    [after] = restored.conflicts
    assert after.conflict_id == before.conflict_id
    assert after.candidate_provenance_hashes == before.candidate_provenance_hashes
    assert after.chosen_provenance_hash == before.chosen_provenance_hash


def test_human_resolution_rejects_new_decision_candidate_in_same_request() -> None:
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
    [conflict] = conflicted.conflicts
    resolution = StateConflictResolution(
        field_path="business.cash",
        conflict_id=conflict.conflict_id,
        selected_provenance_hash=conflict.chosen_provenance_hash,
        resolved_by="operator:finance-owner",
        resolved_at_ms=2_450,
        evidence_refs=(StateEvidenceRef(evidence_id="resolution-ticket-19", kind="human_resolution"),),
    )
    with pytest.raises(ValueError, match="conflict changed by new candidate"):
        engine.synthesize(
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
                        kind="fact",
                        authoritative=True,
                    ),
                ),
                base_snapshot=conflicted,
                conflict_resolutions=(resolution,),
            )
        )


def test_snapshot_roundtrip_rejects_tampered_conflict_identity() -> None:
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
    payload = snapshot.to_dict()
    payload["conflicts"][0]["conflict_id"] = "tampered-conflict-id"
    with pytest.raises(ValueError, match="does not match conflict candidate identity"):
        snapshot_from_dict(payload)


def test_state_audit_trail_records_full_human_resolution_envelope(tmp_path) -> None:
    from runtime.state import FileStateAuditTrail

    audit_path = tmp_path / "state-audit.jsonl"
    engine = StateSynthesisEngine(audit_trail=FileStateAuditTrail(audit_path))
    bank_a = semantic_observation(
        field_path="business.cash", value=100, source="bank:a", observed_at_ms=1_500, kind="fact", authoritative=True
    )
    bank_b = semantic_observation(
        field_path="business.cash", value=120, source="bank:b", observed_at_ms=1_400, kind="fact", authoritative=True
    )
    conflicted = engine.synthesize(_request(bank_a, bank_b))
    [conflict] = conflicted.conflicts
    hashes = dict(zip(conflict.candidate_sources, conflict.candidate_provenance_hashes, strict=True))
    resolution = StateConflictResolution(
        field_path="business.cash",
        conflict_id=conflict.conflict_id,
        selected_provenance_hash=hashes["bank:b"],
        resolved_by="operator:finance-owner",
        resolved_at_ms=2_450,
        evidence_refs=(
            StateEvidenceRef(evidence_id="resolution-ticket-audit", kind="human_resolution", observed_at_ms=2_450),
        ),
    )
    engine.synthesize(
        StateSynthesisRequest(
            tenant_id="tenant-1",
            business_id="business-1",
            now_ms=2_500,
            observations=(bank_b,),
            base_snapshot=conflicted,
            conflict_resolutions=(resolution,),
        )
    )
    import json

    last = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[-1])
    [stored] = last["conflict_resolutions"]
    assert stored["conflict_id"] == conflict.conflict_id
    assert stored["resolved_by"] == "operator:finance-owner"
    assert stored["selected_provenance_hash"] == hashes["bank:b"]
    assert stored["evidence_refs"][0]["evidence_id"] == "resolution-ticket-audit"


def test_request_rejects_caller_supplied_inherited_provenance_hash() -> None:
    spoofed = semantic_observation(
        field_path="business.cash",
        value=999,
        source="untrusted:caller",
        observed_at_ms=1_900,
        kind="fact",
        authoritative=True,
        meta={"inherited_provenance_hash": "a" * 64},
    )
    with pytest.raises(ValueError, match="reserved for internal snapshot rehydration"):
        StateSynthesisRequest(
            tenant_id="tenant-1",
            business_id="business-1",
            now_ms=2_000,
            observations=(spoofed,),
        )


def test_conflict_identity_is_bound_to_tenant_and_business_scope() -> None:
    def conflict_for(tenant_id: str, business_id: str):
        snapshot = StateSynthesisEngine().synthesize(
            StateSynthesisRequest(
                tenant_id=tenant_id,
                business_id=business_id,
                now_ms=2_000,
                observations=(
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
                ),
            )
        )
        [conflict] = snapshot.conflicts
        return conflict

    first = conflict_for("tenant-1", "business-1")
    second = conflict_for("tenant-2", "business-2")
    assert first.tenant_id == "tenant-1"
    assert first.business_id == "business-1"
    assert second.tenant_id == "tenant-2"
    assert second.business_id == "business-2"
    assert first.conflict_id != second.conflict_id


def test_legacy_unscoped_conflict_snapshot_migrates_to_scoped_identity() -> None:
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
    payload = snapshot.to_dict()
    payload["schema_version"] = "state_synthesis@v1"
    payload["conflicts"][0].pop("tenant_id")
    payload["conflicts"][0].pop("business_id")
    payload["conflicts"][0]["conflict_id"] = "legacy-unscoped-conflict-id"
    restored = migrate_legacy_snapshot_from_dict(payload)
    [conflict] = restored.conflicts
    assert conflict.tenant_id == "tenant-1"
    assert conflict.business_id == "business-1"
    assert conflict.conflict_id != "legacy-unscoped-conflict-id"
