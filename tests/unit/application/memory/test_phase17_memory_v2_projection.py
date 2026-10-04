from __future__ import annotations

from application.memory.business_memory_v2 import (
    MEMORY_LIFECYCLE,
    project_business_memory_v2,
    project_memory_knowledge_graph,
)
from application.memory.business_operating_memory import FileBusinessOperatingMemoryStore


def _memory(tmp_path):
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "memory")
    store.remember_execution(
        tenant_id="tenant-1",
        business_id="business-1",
        run_id="run-1",
        goal="increase conversion",
        completed=True,
        stop_reason="goal_reached",
        final_feedback={
            "verified": True,
            "verification_status": "verified",
            "goal_reached": True,
            "normalized_outcome": {"conversion": "improved"},
        },
        step_count=2,
        profile={"segment": "services"},
        constraints={"budget_cap": 1000},
        signals=[{"kind": "metric", "name": "conversion", "value": "up"}],
        meta={"channel": "seo"},
        channel="seo",
        region="eu",
        product_name="growth",
        recorded_at="2026-10-04T00:00:00Z",
    )
    return store.load(tenant_id="tenant-1", business_id="business-1")


def test_memory_v2_separates_canonical_memory_domains_without_copying_external_owners(tmp_path):
    view = project_business_memory_v2(_memory(tmp_path))

    assert tuple(view["lifecycle"]) == MEMORY_LIFECYCLE
    assert view["scope"] == {"tenant_id": "tenant-1", "business_id": "business-1"}
    assert view["operational_state"] == {"owner": "WorldModel", "stored_here": False}
    assert view["evidence_store"]["owner"] == "EvidenceStore"
    assert view["evidence_store"]["stored_here"] is False
    assert view["episodic_memory"][0]["run_id"] == "run-1"
    assert view["semantic_memory"]["business_profile"]["segment"] == "services"
    assert view["business_preferences"]["channel"] == "seo"
    assert view["strategic_memory"][0]["why"] == "increase conversion"
    assert view["strategic_memory"][0]["result"] == "completed"
    assert view["evidence_only"] is True
    assert view["must_not_issue_decision"] is True


def test_memory_v2_procedural_memory_carries_evidence_sample_scope_and_confidence(tmp_path):
    view = project_business_memory_v2(_memory(tmp_path))
    row = next(item for item in view["procedural_memory"] if item["kind"] == "success_pattern")

    assert row["sample_size"] >= 1
    assert row["scope"] == {"tenant_id": "tenant-1", "business_id": "business-1"}
    assert row["evidence"] == ["run-1"]
    assert 0.0 <= row["confidence"] <= 1.0


def test_memory_v2_knowledge_graph_is_projection_only_and_business_scoped(tmp_path):
    graph = project_memory_knowledge_graph(_memory(tmp_path))

    assert graph["projection_only"] is True
    assert graph["source_of_truth"] is False
    assert graph["scope"] == {"tenant_id": "tenant-1", "business_id": "business-1"}
    assert graph["nodes"][0] == {"id": "business:business-1", "kind": "business"}
    assert all(edge["from"] == "business:business-1" for edge in graph["edges"])
