from __future__ import annotations

from pathlib import Path

from application.decision_state.world_model_metadata import attach_world_model_metadata
from contracts.world_model_semantics import WORLD_MODEL_SEMANTIC_KINDS
from kernel.world_state import WorldStateV1
from runtime.state import (
    FileStateSnapshotStore,
    StateEvidenceRef,
    StateSynthesisEngine,
    StateSynthesisRequest,
    semantic_observation,
)


def test_phase2_world_model_survives_replay_and_reaches_decision_metadata(tmp_path: Path) -> None:
    store = FileStateSnapshotStore(tmp_path)
    engine = StateSynthesisEngine(snapshot_store=store)
    evidence = StateEvidenceRef(
        evidence_id="evidence-phase2",
        kind="ledger",
        uri="ledger://phase2/1",
        observed_at_ms=1_100,
    )
    snapshot = engine.synthesize(
        StateSynthesisRequest(
            tenant_id="tenant-phase2",
            business_id="business-phase2",
            now_ms=2_000,
            observations=(
                semantic_observation(
                    field_path="finance.cash",
                    value=125_00,
                    source="ledger",
                    observed_at_ms=1_100,
                    recorded_at_ms=1_150,
                    occurred_at_ms=1_000,
                    valid_from_ms=1_000,
                    valid_until_ms=10_000,
                    kind="fact",
                    confidence=0.95,
                    authoritative=True,
                    ttl_ms=5_000,
                    evidence_refs=(evidence,),
                ),
            ),
        )
    )
    loaded = store.load_latest(tenant_id="tenant-phase2", business_id="business-phase2")
    assert loaded is not None and loaded.semantic_view is not None
    assert snapshot.semantic_view is not None
    assert loaded.semantic_view.as_dict() == snapshot.semantic_view.as_dict()

    state = WorldStateV1(
        schema_version=1,
        user={},
        session={},
        product={},
        economy={},
        timestamp_ms=2_000,
        tenant_id="tenant-phase2",
        world_model_semantics=loaded.semantic_view,
    )
    payload = attach_world_model_metadata(envelope_payload={"decision_id": "decision-phase2"}, state=state)
    assert payload["world_model_meta"]["semantic_state_id"] == loaded.state_id
    assert payload["world_model_meta"]["evidence_refs"] == ["evidence-phase2"]


def test_phase2_audit_is_locked_to_proven_architecture() -> None:
    assert WORLD_MODEL_SEMANTIC_KINDS == (
        "fact", "state", "belief", "assumption", "goal", "constraint", "opportunity",
        "risk", "hypothesis", "forecast", "preference", "recommendation", "unknown",
    )
    text = Path("docs/canon/BUSINESSAIOS_NEXT_PHASE0_AUDIT.md").read_text(encoding="utf-8")
    phase2 = next(line for line in text.splitlines() if line.startswith("| 2 | World Model v1 |"))
    assert "| **DONE** |" in phase2
    assert "StateSynthesisEngine" in phase2
    assert "without a second World Model" in phase2
    assert "Phase 2 cannot be called DONE" not in text
