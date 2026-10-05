from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from application.autonomy.autonomy_state_assembly import AutonomyStateAssembly
from application.memory.business_memory_state_adapter import BusinessMemoryStateAdapter
from application.memory.business_operating_memory import (
    MEMORY_LIFECYCLE,
    BusinessMemoryCompactor,
    BusinessOperatingMemory,
    FileBusinessOperatingMemoryStore,
    add_memory_candidate,
    persist_memory_candidate,
    persist_memory_transition,
    project_business_memory_v2,
    project_memory_knowledge_graph,
    project_portable_memory,
    transition_memory,
)
from application.memory.business_operating_memory_types import AntiPatternRecord, DurableMemoryRecord, PatternEvidence
from kernel.world_state import WorldStateV1


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
                "from application.memory.business_operating_memory import project_business_memory_v2; "
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
    assert all(item.memory_id != "mem-2" for item in reloaded.durable_memory)
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



def test_atomic_memory_mutation_preserves_concurrent_candidates(tmp_path):
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "memory")
    records = [
        DurableMemoryRecord(memory_id=f"mem-race-{idx}", memory_type="semantic", key=f"k-{idx}", value=f"v-{idx}")
        for idx in range(2)
    ]

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(
            lambda record: persist_memory_candidate(
                store,
                tenant_id="tenant-race",
                business_id="business-race",
                record=record,
            ),
            records,
        ))

    loaded = store.load(tenant_id="tenant-race", business_id="business-race")
    assert {item.memory_id for item in loaded.durable_memory} == {"mem-race-0", "mem-race-1"}


def test_persisted_external_candidate_stays_quarantined_across_restart_until_validation(tmp_path):
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "memory")
    persist_memory_candidate(
        store,
        tenant_id="tenant-q",
        business_id="business-q",
        record=DurableMemoryRecord(
            memory_id="mem-q",
            memory_type="semantic",
            key="external_signal",
            value="untrusted",
            external=True,
        ),
    )
    restarted = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "memory")
    quarantined = restarted.load(tenant_id="tenant-q", business_id="business-q")
    assert project_business_memory_v2(quarantined)["durable_memory"] == []

    validated = persist_memory_transition(
        restarted,
        tenant_id="tenant-q",
        business_id="business-q",
        memory_id="mem-q",
        transition="validate",
        provenance=("source-proof",),
    )
    assert project_business_memory_v2(validated)["durable_memory"][0]["memory_id"] == "mem-q"



def test_execution_write_and_lifecycle_write_do_not_lose_each_other(tmp_path):
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "memory")
    candidate = DurableMemoryRecord(
        memory_id="mem-shared",
        memory_type="semantic",
        key="customer_signal",
        value="validated later",
    )

    def remember():
        return store.remember_execution(
            tenant_id="tenant-shared",
            business_id="business-shared",
            run_id="run-shared",
            goal="grow",
            completed=True,
            stop_reason="goal_reached",
            final_feedback={"goal_score": 0.9, "goal_reached": True},
            step_count=1,
            profile={"segment": "services"},
            constraints={},
            signals=[],
            meta={},
            channel="headless",
            region="eu",
            product_name="BusinessAIOS",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(remember),
            pool.submit(
                persist_memory_candidate,
                store,
                tenant_id="tenant-shared",
                business_id="business-shared",
                record=candidate,
            ),
        ]
        for future in futures:
            future.result()

    loaded = store.load(tenant_id="tenant-shared", business_id="business-shared")
    assert loaded.total_runs == 1
    assert loaded.recent_runs[0].run_id == "run-shared"
    assert {item.memory_id for item in loaded.durable_memory} == {"mem-shared"}


def test_full_lifecycle_supports_supersede_expire_archive_and_forget(tmp_path):
    memory = add_memory_candidate(
        _memory(tmp_path),
        DurableMemoryRecord(
            memory_id="mem-life",
            memory_type="semantic",
            key="offer",
            value="v1",
            provenance=("run-1",),
        ),
    )
    validated = transition_memory(memory, memory_id="mem-life", transition="validate")
    superseded = transition_memory(validated, memory_id="mem-life", transition="supersede")
    archived = transition_memory(superseded, memory_id="mem-life", transition="archive")
    forgotten = transition_memory(archived, memory_id="mem-life", transition="forget")
    assert forgotten.durable_memory == ()

    expiring = transition_memory(validated, memory_id="mem-life", transition="expire")
    assert expiring.durable_memory[0].status == "expire"
    assert transition_memory(expiring, memory_id="mem-life", transition="archive").durable_memory[0].status == "archive"


def test_schema_v2_memory_migrates_to_v3_without_inventing_durable_memory(tmp_path):
    root = tmp_path / "memory"
    target = root / "tenant-old"
    target.mkdir(parents=True)
    (target / "business-old.json").write_text(
        '{"schema_version":2,"tenant_id":"tenant-old","business_id":"business-old","business_profile":{"segment":"legacy"}}',
        encoding="utf-8",
    )
    loaded = FileBusinessOperatingMemoryStore(root_dir=root).load(
        tenant_id="tenant-old",
        business_id="business-old",
    )
    assert loaded.schema_version == 3
    assert loaded.business_profile == {"segment": "legacy"}
    assert loaded.durable_memory == ()



def test_anti_pattern_sample_size_uses_originating_failure_count_not_capped_refs():
    memory = BusinessOperatingMemory(
        schema_version=3,
        tenant_id="tenant-1",
        business_id="business-1",
        recurring_failures=(
            PatternEvidence(
                key="timeout",
                count=10,
                confidence=0.9,
                frequency=0.8,
                freshness=1.0,
                source_run_ids=tuple(f"run-{idx}" for idx in range(8)),
            ),
        ),
        anti_patterns=(
            AntiPatternRecord(
                key="timeout",
                confidence=0.9,
                frequency=0.8,
                freshness=1.0,
                source_run_ids=tuple(f"run-{idx}" for idx in range(8)),
            ),
        ),
    )
    view = project_business_memory_v2(memory)
    anti = next(item for item in view["procedural_memory"] if item["kind"] == "anti_pattern")
    assert anti["sample_size"] == 10
    assert len(anti["evidence"]) == 8



def test_state_assembly_prefers_canonical_store_over_stale_legacy_memory_context(tmp_path):
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "memory")
    persist_memory_candidate(
        store,
        tenant_id="tenant-live",
        business_id="business-live",
        record=DurableMemoryRecord(
            memory_id="mem-live",
            memory_type="semantic",
            key="validated_fact",
            value="store truth",
        ),
    )
    persist_memory_transition(
        store,
        tenant_id="tenant-live",
        business_id="business-live",
        memory_id="mem-live",
        transition="validate",
        provenance=("proof-1",),
    )

    class Mapper:
        def to_world_state(self, *, request, step_index, previous_feedback):
            return WorldStateV1(
                schema_version=1,
                user={"user_id": "u1"},
                session={"channel": "headless"},
                product={"business_id": request.business_id},
                economy={},
                timestamp_ms=1,
                tenant_id=request.tenant_id,
                meta={},
                behavior={"goal": request.goal},
            )

    class Trace:
        run_id = "run-live"

        def record(self, **kwargs):
            return None

    contract = SimpleNamespace(
        _state_mapper=Mapper(),
        _business_memory_state_adapter=BusinessMemoryStateAdapter(store=store),
        _capability_health_registry=None,
        _capability_health_scoring_service=None,
        _event_store=None,
        _provider_quota_guard=None,
        _state_store=None,
    )
    request = SimpleNamespace(
        tenant_id="tenant-live",
        business_id="business-live",
        goal="grow",
        goal_id=None,
        meta={},
    )
    state = AutonomyStateAssembly(contract=contract).assemble_state(
        request=request,
        trace=Trace(),
        step_index=0,
        previous_feedback={},
        business_memory_context={
            "tenant_id": "tenant-live",
            "business_id": "business-live",
            "business_profile": {"stale": "legacy"},
        },
    )

    durable = state.meta["business_memory_v2"]["durable_memory"]
    assert durable[0]["memory_id"] == "mem-live"
    assert durable[0]["value"] == "store truth"



def test_blank_provenance_cannot_activate_or_survive_reload(tmp_path):
    memory = add_memory_candidate(
        _memory(tmp_path),
        DurableMemoryRecord(
            memory_id="mem-blank",
            memory_type="semantic",
            key="external",
            value="claim",
            external=True,
        ),
    )
    try:
        transition_memory(memory, memory_id="mem-blank", transition="validate", provenance=("   ",))
    except ValueError as exc:
        assert "requires provenance" in str(exc)
    else:
        raise AssertionError("blank provenance activated memory")

    root = tmp_path / "crafted"
    target = root / "tenant-1"
    target.mkdir(parents=True)
    (target / "business-1.json").write_text(
        '{"schema_version":3,"tenant_id":"tenant-1","business_id":"business-1","durable_memory":[{"memory_id":"mem-crafted","memory_type":"semantic","key":"external","value":"claim","status":"validate","provenance":["   "],"external":true}]}',
        encoding="utf-8",
    )
    loaded = FileBusinessOperatingMemoryStore(root_dir=root).load(
        tenant_id="tenant-1",
        business_id="business-1",
    )
    crafted = next(item for item in loaded.durable_memory if item.memory_id == "mem-crafted")
    assert crafted.status == "create"
    assert crafted.provenance == ()
    assert project_business_memory_v2(loaded)["durable_memory"] == []


def test_quarantine_cannot_evict_validated_memory_during_compaction():
    active = DurableMemoryRecord(
        memory_id="trusted",
        memory_type="semantic",
        key="trusted",
        value="verified",
        status="validate",
        provenance=("proof",),
    )
    quarantine = tuple(
        DurableMemoryRecord(
            memory_id=f"q-{idx}",
            memory_type="semantic",
            key=f"q-{idx}",
            value="untrusted",
            external=True,
        )
        for idx in range(80)
    )
    memory = BusinessOperatingMemory(
        schema_version=3,
        tenant_id="tenant-1",
        business_id="business-1",
        durable_memory=quarantine + (active,),
    )
    compacted = BusinessMemoryCompactor().compact(memory)
    assert any(item.memory_id == "trusted" for item in compacted.durable_memory)
    assert len(compacted.durable_memory) <= 64


def test_read_time_migration_is_persisted_atomically(tmp_path):
    root = tmp_path / "persist-migration"
    target = root / "tenant-old"
    target.mkdir(parents=True)
    path = target / "business-old.json"
    path.write_text(
        '{"schema_version":2,"tenant_id":"tenant-old","business_id":"business-old","business_profile":{"segment":"legacy"}}',
        encoding="utf-8",
    )
    FileBusinessOperatingMemoryStore(root_dir=root).load(
        tenant_id="tenant-old",
        business_id="business-old",
    )
    persisted = __import__("json").loads(path.read_text(encoding="utf-8"))
    assert persisted["schema_version"] == 3
    assert persisted["durable_memory"] == []


def test_future_schema_load_fails_closed_without_rewrite(tmp_path):
    root = tmp_path / "future-schema"
    target = root / "tenant-future"
    target.mkdir(parents=True)
    path = target / "business-future.json"
    original = '{"schema_version":4,"tenant_id":"tenant-future","business_id":"business-future","future_only":{"keep":true}}'
    path.write_text(original, encoding="utf-8")
    try:
        FileBusinessOperatingMemoryStore(root_dir=root).load(
            tenant_id="tenant-future",
            business_id="business-future",
        )
    except ValueError as exc:
        assert "unsupported future business memory schema" in str(exc)
    else:
        raise AssertionError("future memory schema was silently downgraded")
    assert path.read_text(encoding="utf-8") == original


def test_mismatched_persisted_scope_fails_closed_without_cross_scope_rewrite(tmp_path):
    root = tmp_path / "scope-mismatch"
    source_dir = root / "tenant-a"
    target_dir = root / "tenant-b"
    source_dir.mkdir(parents=True)
    target_dir.mkdir(parents=True)
    source = source_dir / "business-a.json"
    target = target_dir / "business-b.json"
    source_payload = '{"schema_version":2,"tenant_id":"tenant-b","business_id":"business-b","business_profile":{"source":"wrong-scope"}}'
    target_payload = '{"schema_version":3,"tenant_id":"tenant-b","business_id":"business-b","business_profile":{"source":"legitimate"}}'
    source.write_text(source_payload, encoding="utf-8")
    target.write_text(target_payload, encoding="utf-8")

    store = FileBusinessOperatingMemoryStore(root_dir=root)
    try:
        store.load(tenant_id="tenant-a", business_id="business-a")
    except ValueError as exc:
        assert "persisted scope mismatch" in str(exc)
    else:
        raise AssertionError("mismatched persisted scope was accepted")

    assert source.read_text(encoding="utf-8") == source_payload
    assert target.read_text(encoding="utf-8") == target_payload
    assert store.list_businesses(tenant_id="tenant-a") == ()
    assert store.list_businesses() == (("tenant-b", "business-b"),)


def test_noncanonical_long_requested_scope_cannot_rewrite_truncated_scope(tmp_path):
    root = tmp_path / "long-scope"
    long_tenant = "t" * 129
    canonical_tenant = "t" * 128
    source_dir = root / long_tenant
    target_dir = root / canonical_tenant
    source_dir.mkdir(parents=True)
    target_dir.mkdir(parents=True)
    source = source_dir / "business-a.json"
    target = target_dir / "business-a.json"
    source_payload = (
        '{"schema_version":2,"tenant_id":"' + long_tenant
        + '","business_id":"business-a","business_profile":{"source":"long-scope"}}'
    )
    target_payload = (
        '{"schema_version":3,"tenant_id":"' + canonical_tenant
        + '","business_id":"business-a","business_profile":{"source":"legitimate"}}'
    )
    source.write_text(source_payload, encoding="utf-8")
    target.write_text(target_payload, encoding="utf-8")

    store = FileBusinessOperatingMemoryStore(root_dir=root)
    try:
        store.load(tenant_id=long_tenant, business_id="business-a")
    except ValueError as exc:
        assert "persisted scope mismatch" in str(exc)
    else:
        raise AssertionError("noncanonical long scope was accepted")

    assert source.read_text(encoding="utf-8") == source_payload
    assert target.read_text(encoding="utf-8") == target_payload



def test_direct_save_cannot_overwrite_colliding_scope_key(tmp_path):
    root = tmp_path / "scope-key-collision"
    store = FileBusinessOperatingMemoryStore(root_dir=root)
    original = BusinessOperatingMemory.empty(
        tenant_id="tenant-1",
        business_id="business/a",
    )
    original_path = store.save(original)
    original_bytes = original_path.read_bytes()

    colliding = BusinessOperatingMemory.empty(
        tenant_id="tenant-1",
        business_id="business_a",
    )
    try:
        store.save(colliding)
    except ValueError as exc:
        assert "persisted scope mismatch" in str(exc)
    else:
        raise AssertionError("colliding scope key overwrote another business memory")

    assert original_path.read_bytes() == original_bytes
    assert store.load(tenant_id="tenant-1", business_id="business/a").business_id == "business/a"


def test_scope_path_escape_is_rejected_before_filesystem_write(tmp_path):
    root = tmp_path / "path-escape"
    store = FileBusinessOperatingMemoryStore(root_dir=root)
    escaped = tmp_path / "business-1.json"

    try:
        store.save(BusinessOperatingMemory.empty(tenant_id="..", business_id="business-1"))
    except ValueError as exc:
        assert "business memory path escapes root" in str(exc)
    else:
        raise AssertionError("path-escaping tenant scope was accepted")

    assert not escaped.exists()


def test_persisted_durable_flags_require_real_booleans():
    base = {
        "schema_version": 3,
        "tenant_id": "tenant-1",
        "business_id": "business-1",
        "durable_memory": [{
            "memory_id": "portable-1",
            "memory_type": "semantic",
            "key": "portable",
            "value": "value",
            "status": "validate",
            "provenance": ["proof-1"],
            "portable": True,
            "anonymized": True,
            "external": False,
        }],
    }
    for field_name, invalid_value in (
        ("portable", "false"),
        ("anonymized", 1),
        ("external", 0),
        ("portable", None),
    ):
        payload = __import__("copy").deepcopy(base)
        payload["durable_memory"][0][field_name] = invalid_value
        try:
            BusinessOperatingMemory.from_dict(payload)
        except ValueError as exc:
            assert "durable memory flags must be boolean" in str(exc)
        else:
            raise AssertionError(f"malformed {field_name} flag was accepted")



def test_malformed_numeric_trust_signals_fall_back_to_safe_defaults():
    payload = {
        "schema_version": 3,
        "tenant_id": "tenant-1",
        "business_id": "business-1",
        "durable_memory": [{
            "memory_id": "numeric-1",
            "memory_type": "semantic",
            "key": "numeric",
            "value": "value",
            "status": "validate",
            "provenance": ["proof-1"],
            "confidence": True,
            "sample_size": True,
            "portable": False,
            "anonymized": False,
            "external": False,
        }],
    }
    memory = BusinessOperatingMemory.from_dict(payload)
    assert memory.durable_memory[0].confidence == 0.0
    assert memory.durable_memory[0].sample_size == 0

    payload["durable_memory"][0]["confidence"] = "nan"
    memory = BusinessOperatingMemory.from_dict(payload)
    assert memory.durable_memory[0].confidence == 0.0

    payload["durable_memory"][0]["confidence"] = "inf"
    memory = BusinessOperatingMemory.from_dict(payload)
    assert memory.durable_memory[0].confidence == 0.0

def test_corrupt_persisted_json_fails_closed_without_rewrite(tmp_path):
    root = tmp_path / "corrupt-json"
    target = root / "tenant-1"
    target.mkdir(parents=True)
    path = target / "business-1.json"
    original = "{not-json"
    path.write_text(original, encoding="utf-8")
    store = FileBusinessOperatingMemoryStore(root_dir=root)

    try:
        store.load(tenant_id="tenant-1", business_id="business-1")
    except ValueError as exc:
        assert "corrupt business memory persistence" in str(exc)
    else:
        raise AssertionError("corrupt persisted JSON was silently accepted")

    assert path.read_text(encoding="utf-8") == original


def test_scalar_provenance_cannot_activate_or_export_portable_memory():
    payload = {
        "schema_version": 3,
        "tenant_id": "tenant-1",
        "business_id": "business-1",
        "durable_memory": [{
            "memory_id": "portable-scalar-proof",
            "memory_type": "semantic",
            "key": "portable",
            "value": "value",
            "status": "validate",
            "provenance": "proof",
            "portable": True,
            "anonymized": True,
            "external": True,
        }],
    }
    try:
        BusinessOperatingMemory.from_dict(payload)
    except ValueError as exc:
        assert "run id references must be a list or tuple" in str(exc)
    else:
        raise AssertionError("scalar provenance was accepted as evidence references")

    payload["durable_memory"][0]["provenance"] = [1]
    try:
        BusinessOperatingMemory.from_dict(payload)
    except ValueError as exc:
        assert "list or tuple of strings" in str(exc)
    else:
        raise AssertionError("non-string persisted provenance was accepted")


def test_tenant_scoped_listing_rejects_safe_key_collision(tmp_path):
    root = tmp_path / "tenant-list-collision"
    store = FileBusinessOperatingMemoryStore(root_dir=root)
    store.save(BusinessOperatingMemory.empty(tenant_id="tenant_a", business_id="business-1"))

    assert store.list_businesses(tenant_id="tenant_a") == (("tenant_a", "business-1"),)
    assert store.list_businesses(tenant_id="tenant/a") == ()


def test_huge_sample_size_is_capped_before_payload_budget(tmp_path):
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "sample-budget")
    memory = BusinessOperatingMemory.from_dict({
        "schema_version": 3,
        "tenant_id": "tenant-1",
        "business_id": "business-1",
        "durable_memory": [
            {
                "memory_id": f"sample-{index}",
                "memory_type": "semantic",
                "key": f"key-{index}",
                "value": "value",
                "status": "validate",
                "provenance": [f"proof-{index}"],
                "sample_size": 10 ** 4000,
            }
            for index in range(16)
        ],
    })

    path = store.save(memory)
    reloaded = store.load(tenant_id="tenant-1", business_id="business-1")

    assert path.stat().st_size <= store.policy.approx_hard_payload_bytes
    assert all(item.sample_size == store.policy.max_durable_memory_sample_size for item in reloaded.durable_memory)


def test_explicit_malformed_schema_versions_fail_closed_without_rewrite(tmp_path):
    for index, schema_version in enumerate((None, "future", 3.5, True)):
        root = tmp_path / f"malformed-schema-{index}"
        target = root / "tenant-1"
        target.mkdir(parents=True)
        path = target / "business-1.json"
        payload = {
            "schema_version": schema_version,
            "tenant_id": "tenant-1",
            "business_id": "business-1",
            "unknown_future_field": {"must": "survive"},
        }
        original = __import__("json").dumps(payload, ensure_ascii=False)
        path.write_text(original, encoding="utf-8")
        store = FileBusinessOperatingMemoryStore(root_dir=root)

        try:
            store.load(tenant_id="tenant-1", business_id="business-1")
        except ValueError as exc:
            assert "malformed schema version" in str(exc)
        else:
            raise AssertionError(f"explicit malformed schema {schema_version!r} was accepted")

        assert path.read_text(encoding="utf-8") == original


def test_transition_rejects_scalar_provenance_before_activation():
    memory = BusinessOperatingMemory(
        schema_version=3,
        tenant_id="tenant-1",
        business_id="business-1",
        durable_memory=(
            DurableMemoryRecord(
                memory_id="transition-proof-shape",
                memory_type="semantic",
                key="proof-shape",
                value="value",
            ),
        ),
    )
    try:
        transition_memory(
            memory,
            memory_id="transition-proof-shape",
            transition="validate",
            provenance="proof",
        )
    except ValueError as exc:
        assert "transition provenance must be a list or tuple" in str(exc)
    else:
        raise AssertionError("scalar transition provenance was accepted")

    try:
        transition_memory(
            memory,
            memory_id="transition-proof-shape",
            transition="validate",
            provenance=(1,),
        )
    except ValueError as exc:
        assert "list or tuple of strings" in str(exc)
    else:
        raise AssertionError("non-string transition provenance was accepted")


def test_normalized_memory_id_collision_fails_closed_at_save_boundary(tmp_path):
    prefix = "x" * 128
    memory = BusinessOperatingMemory(
        schema_version=3,
        tenant_id="tenant-1",
        business_id="business-1",
        durable_memory=(
            DurableMemoryRecord(
                memory_id=prefix + "a",
                memory_type="semantic",
                key="first",
                value="first",
            ),
            DurableMemoryRecord(
                memory_id=prefix + "b",
                memory_type="semantic",
                key="second",
                value="second",
            ),
        ),
    )
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "normalized-id-collision")

    try:
        store.save(memory)
    except ValueError as exc:
        assert "normalized durable memory_id collision" in str(exc)
    else:
        raise AssertionError("normalized duplicate memory ids were persisted")

    assert tuple((tmp_path / "normalized-id-collision").rglob("*.json")) == ()


def test_multibyte_durable_memory_is_trimmed_to_measured_utf8_ceiling(tmp_path):
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "multibyte-budget")
    memory = BusinessOperatingMemory.from_dict({
        "schema_version": 3,
        "tenant_id": "tenant-1",
        "business_id": "business-1",
        "durable_memory": [
            {
                "memory_id": f"emoji-{index}",
                "memory_type": "semantic",
                "key": "😀" * 160,
                "value": "😀" * 512,
                "status": "validate",
                "provenance": [f"proof-{index}-{proof}-" + ("😀" * 100) for proof in range(8)],
                "confidence": 0.9,
                "sample_size": 100,
            }
            for index in range(16)
        ],
    })

    path = store.save(memory)
    reloaded = store.load(tenant_id="tenant-1", business_id="business-1")

    assert path.stat().st_size <= store.policy.approx_hard_payload_bytes
    assert len(reloaded.durable_memory) < 16


def test_listing_path_escape_is_rejected_before_glob(tmp_path):
    root = tmp_path / "listing-root"
    store = FileBusinessOperatingMemoryStore(root_dir=root)
    try:
        store.list_businesses(tenant_id="..")
    except ValueError as exc:
        assert "business memory path escapes root" in str(exc)
    else:
        raise AssertionError("path-escaping tenant listing scope was accepted")


def test_second_load_read_corruption_fails_closed(tmp_path, monkeypatch):
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "second-read")
    path = store.save(BusinessOperatingMemory.empty(tenant_id="tenant-1", business_id="business-1"))
    original_read_text = path.__class__.read_text
    calls = {"count": 0}

    def _read_text(self, *args, **kwargs):
        if self == path:
            calls["count"] += 1
            if calls["count"] == 2:
                return "{not-json"
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(path.__class__, "read_text", _read_text)
    try:
        store.load(tenant_id="tenant-1", business_id="business-1")
    except ValueError as exc:
        assert "corrupt business memory persistence" in str(exc)
    else:
        raise AssertionError("corrupt second persistence read was silently ignored")

def test_persistence_boundary_sanitizes_oversized_durable_memory_fields(tmp_path):
    root = tmp_path / "durable-ceiling"
    store = FileBusinessOperatingMemoryStore(root_dir=root)
    memory = add_memory_candidate(
        BusinessOperatingMemory.empty(tenant_id="tenant-1", business_id="business-1"),
        DurableMemoryRecord(
            memory_id="memory-oversized",
            memory_type="semantic",
            key="oversized",
            value="x" * 100_000,
            provenance=tuple(f"proof-{index}-" + ("y" * 300) for index in range(100)),
        ),
    )

    path = store.save(memory)
    assert path.stat().st_size <= store.policy.approx_hard_payload_bytes
    persisted = __import__("json").loads(path.read_text(encoding="utf-8"))
    durable = persisted["durable_memory"][0]
    assert len(durable["value"]) <= store.policy.max_summary_length
    assert len(durable["provenance"]) <= store.policy.max_source_run_ids
    assert all(len(item) <= 128 for item in durable["provenance"])

    loaded = store.load(tenant_id="tenant-1", business_id="business-1")
    assert loaded.durable_memory[0].status == "create"
    assert loaded.durable_memory[0].memory_id == "memory-oversized"



def test_persisted_payload_matches_compactor_byte_budget(tmp_path):
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "serialized-budget")
    memory = BusinessOperatingMemory(
        schema_version=3,
        tenant_id="tenant-1",
        business_id="business-1",
        durable_memory=tuple(
            DurableMemoryRecord(
                memory_id=f"memory-{index}",
                memory_type="semantic",
                key=("k" * 150) + str(index),
                value=("v" * 500) + str(index),
                provenance=tuple(f"proof-{index}-{proof}-" + ("p" * 100) for proof in range(8)),
            )
            for index in range(24)
        ),
    )
    canonical = BusinessOperatingMemory.from_dict(memory.to_dict(), policy=store.policy)
    assert store.compactor is not None
    _compacted, report = store.compactor.compact_with_report(canonical)

    path = store.save(memory)

    assert path.stat().st_size == report.approx_payload_bytes
    assert path.stat().st_size <= report.hard_payload_bytes


def test_noncanonical_scope_is_rejected_before_first_mutation_write(tmp_path):
    root = tmp_path / "first-write-scope"
    store = FileBusinessOperatingMemoryStore(root_dir=root)
    try:
        persist_memory_candidate(
            store,
            tenant_id="t" * 129,
            business_id="business-1",
            record=DurableMemoryRecord(
                memory_id="scope-check",
                memory_type="semantic",
                key="scope-check",
                value="must not persist",
            ),
        )
    except ValueError as exc:
        assert "noncanonical business memory scope" in str(exc)
    else:
        raise AssertionError("noncanonical first-write scope was accepted")

    assert tuple(root.rglob("*.json")) == ()

def test_persist_candidate_retry_is_idempotent_after_sanitization(tmp_path):
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "retry-sanitized")
    record = DurableMemoryRecord(
        memory_id="retry-oversized",
        memory_type="semantic",
        key="retry-key",
        value="x" * 100_000,
        provenance=tuple(f"proof-{index}-" + ("y" * 300) for index in range(100)),
    )

    first = persist_memory_candidate(
        store,
        tenant_id="tenant-1",
        business_id="business-1",
        record=record,
    )
    second = persist_memory_candidate(
        store,
        tenant_id="tenant-1",
        business_id="business-1",
        record=record,
    )

    assert second == first
    assert len(second.durable_memory) == 1
    durable = second.durable_memory[0]
    assert len(durable.value) <= store.policy.max_summary_length
    assert len(durable.provenance) <= store.policy.max_source_run_ids
    assert all(len(item) <= 128 for item in durable.provenance)


def test_candidate_identity_is_normalized_before_validation_and_collision():
    memory = BusinessOperatingMemory.empty(tenant_id="tenant-1", business_id="business-1")
    try:
        add_memory_candidate(
            memory,
            DurableMemoryRecord(memory_id="   ", memory_type="semantic", key="valid", value="claim"),
        )
    except ValueError as exc:
        assert "requires memory_id and key" in str(exc)
    else:
        raise AssertionError("blank normalized memory_id was accepted")

    prefix = "m" * 128
    normalized = add_memory_candidate(
        memory,
        DurableMemoryRecord(memory_id=f"{prefix}A", memory_type="semantic", key="  normalized key  ", value="first"),
    )
    assert normalized.durable_memory[0].memory_id == prefix
    assert normalized.durable_memory[0].key == "normalized key"
    transitioned = transition_memory(
        normalized,
        memory_id=f"{prefix}A",
        transition="validate",
        provenance=("proof",),
    )
    assert transitioned.durable_memory[0].status == "validate"
    try:
        add_memory_candidate(
            normalized,
            DurableMemoryRecord(memory_id=f"{prefix}B", memory_type="semantic", key="other", value="second"),
        )
    except ValueError as exc:
        assert "memory_id collision" in str(exc)
    else:
        raise AssertionError("normalized memory_id collision was accepted")


def test_legacy_context_injection_does_not_claim_memory_v2_without_canonical_store():
    adapter = BusinessMemoryStateAdapter(store=None)
    state = WorldStateV1(
        schema_version=1,
        user={"user_id": "u1"},
        session={"channel": "headless"},
        product={"business_id": "business-1"},
        economy={},
        timestamp_ms=1,
        tenant_id="tenant-1",
        meta={},
        behavior={"goal": "grow"},
    )
    enriched = adapter.inject_context(
        world_state=state,
        memory_context={"tenant_id": "tenant-1", "business_id": "business-1"},
    )
    assert "business_memory_v2" not in enriched.meta
