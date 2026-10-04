from __future__ import annotations

import subprocess
import sys

from application.memory.business_memory_v2 import (
    MEMORY_LIFECYCLE,
    add_memory_candidate,
    project_business_memory_v2,
    project_memory_knowledge_graph,
    project_portable_memory,
    transition_memory,
)
from application.memory.business_operating_memory import FileBusinessOperatingMemoryStore
from application.memory.business_operating_memory_types import DurableMemoryRecord


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


def test_memory_v2_imports_in_fresh_process_without_runtime_policy_cycle():
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from application.memory.business_memory_v2 import project_business_memory_v2; "
                "from runtime.platform.business_memory.policy import BusinessMemoryPolicy; "
                "policy = BusinessMemoryPolicy(); "
                "assert policy.max_active_channels == 12; "
                "assert policy.max_verified_outcomes == 20"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert probe.returncode == 0, probe.stderr


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



def test_external_memory_is_quarantined_until_validated_with_provenance(tmp_path):
    memory = _memory(tmp_path)
    candidate = DurableMemoryRecord(
        memory_id="mem-1",
        memory_type="semantic",
        key="market_signal",
        value="external claim",
        external=True,
    )
    created = add_memory_candidate(memory, candidate)
    assert project_business_memory_v2(created)["durable_memory"] == []

    try:
        transition_memory(created, memory_id="mem-1", transition="validate")
    except ValueError as exc:
        assert "requires provenance" in str(exc)
    else:
        raise AssertionError("external durable memory validated without provenance")

    validated = transition_memory(
        created,
        memory_id="mem-1",
        transition="validate",
        provenance=("evidence-1",),
        updated_at="2026-10-04T01:00:00Z",
    )
    row = project_business_memory_v2(validated)["durable_memory"][0]
    assert row["status"] == "validate"
    assert row["provenance"] == ("evidence-1",)


def test_memory_lifecycle_forget_scrubs_content_and_restart_preserves_tombstone(tmp_path):
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "memory")
    memory = _memory(tmp_path)
    created = add_memory_candidate(
        memory,
        DurableMemoryRecord(
            memory_id="mem-2",
            memory_type="strategic",
            key="pricing_test",
            value="do not retry without retention guard",
            provenance=("run-1",),
        ),
    )
    validated = transition_memory(created, memory_id="mem-2", transition="validate")
    refreshed = transition_memory(
        validated,
        memory_id="mem-2",
        transition="refresh",
        provenance=("run-2",),
    )
    forgotten = transition_memory(refreshed, memory_id="mem-2", transition="forget")
    store.save(forgotten)

    reloaded = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "memory").load(
        tenant_id="tenant-1",
        business_id="business-1",
    )
    tombstone = next(item for item in reloaded.durable_memory if item.memory_id == "mem-2")
    assert tombstone.status == "forget"
    assert tombstone.value == ""
    assert tombstone.provenance == ()
    assert project_business_memory_v2(reloaded)["durable_memory"] == []


def test_cross_tenant_memory_isolation_and_portable_projection_are_fail_closed(tmp_path):
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "memory")
    memory = _memory(tmp_path)
    validated = transition_memory(
        add_memory_candidate(
            memory,
            DurableMemoryRecord(
                memory_id="mem-3",
                memory_type="procedural",
                key="offer_pattern",
                value="shorter onboarding converts better",
                portable=True,
                anonymized=True,
            ),
        ),
        memory_id="mem-3",
        transition="validate",
        provenance=("experiment-1",),
    )
    store.save(validated)

    other = store.load(tenant_id="tenant-2", business_id="business-1")
    assert other.durable_memory == ()
    assert project_portable_memory(validated) == []
    portable = project_portable_memory(validated, allow_global=True)
    assert portable == [{
        "memory_type": "procedural",
        "key": "offer_pattern",
        "value": "shorter onboarding converts better",
        "confidence": 0.0,
        "sample_size": 0,
    }]
    assert "tenant_id" not in portable[0]
    assert "business_id" not in portable[0]
    assert "provenance" not in portable[0]


def test_memory_candidate_identity_is_idempotent_but_collision_fails(tmp_path):
    memory = _memory(tmp_path)
    candidate = DurableMemoryRecord(memory_id="mem-4", memory_type="semantic", key="segment", value="clinic")
    once = add_memory_candidate(memory, candidate)
    assert add_memory_candidate(once, candidate) == once

    conflicting = DurableMemoryRecord(memory_id="mem-4", memory_type="semantic", key="segment", value="retail")
    try:
        add_memory_candidate(once, conflicting)
    except ValueError as exc:
        assert "collision" in str(exc)
    else:
        raise AssertionError("memory identity collision was accepted")
