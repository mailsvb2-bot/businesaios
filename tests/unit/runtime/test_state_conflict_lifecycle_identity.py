from __future__ import annotations

import pytest

from runtime.state import (
    StateConflictResolution,
    StateEvidenceRef,
    StateSynthesisEngine,
    StateSynthesisRequest,
    semantic_observation,
    snapshot_from_dict,
)


def _request(*observations):
    return StateSynthesisRequest(
        tenant_id="tenant-1",
        business_id="business-1",
        now_ms=2_000,
        observations=tuple(observations),
        correlation_id="corr-conflict-lifecycle-identity",
    )

def test_state_id_changes_when_conflict_lifecycle_changes_at_same_timestamp() -> None:
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
    resolved = engine.synthesize(
        StateSynthesisRequest(
            tenant_id="tenant-1",
            business_id="business-1",
            now_ms=2_000,
            observations=(),
            base_snapshot=conflicted,
            conflict_resolutions=(
                StateConflictResolution(
                    field_path="business.cash",
                    conflict_id=conflict.conflict_id,
                    selected_provenance_hash=conflict.chosen_provenance_hash,
                    resolved_by="operator:finance-owner",
                    resolved_at_ms=2_000,
                    evidence_refs=(
                        StateEvidenceRef(
                            evidence_id="resolution-ticket-same-time",
                            kind="human_resolution",
                            observed_at_ms=2_000,
                        ),
                    ),
                ),
            ),
        )
    )

    assert conflicted.fields["business.cash"].provenance_hash == resolved.fields["business.cash"].provenance_hash
    assert conflicted.state_id != resolved.state_id
    restored = snapshot_from_dict(resolved.to_dict())
    assert restored.state_id == resolved.state_id
    [restored_conflict] = restored.conflicts
    assert restored_conflict.status == "resolved"

def test_snapshot_identity_rejects_resolution_actor_or_reason_tamper() -> None:
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
    resolved = engine.synthesize(
        StateSynthesisRequest(
            tenant_id="tenant-1",
            business_id="business-1",
            now_ms=2_000,
            observations=(),
            base_snapshot=conflicted,
            conflict_resolutions=(
                StateConflictResolution(
                    field_path="business.cash",
                    conflict_id=conflict.conflict_id,
                    selected_provenance_hash=conflict.chosen_provenance_hash,
                    resolved_by="operator:finance-owner",
                    resolved_at_ms=2_000,
                    evidence_refs=(
                        StateEvidenceRef(
                            evidence_id="resolution-ticket-tamper",
                            kind="human_resolution",
                            observed_at_ms=2_000,
                        ),
                    ),
                    reason="verified by finance owner",
                ),
            ),
        )
    )

    for key, forged in (
        ("resolved_by", "operator:attacker"),
        ("resolution_reason", "forged reason"),
    ):
        payload = resolved.to_dict()
        payload["fields"]["business.cash"]["meta"][key] = forged
        with pytest.raises(ValueError, match="snapshot identity mismatch"):
            snapshot_from_dict(payload)
