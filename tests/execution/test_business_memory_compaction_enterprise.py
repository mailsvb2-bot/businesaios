from __future__ import annotations

import json

from execution.business_memory_compactor import BusinessMemoryCompactor
from execution.business_memory_policy import BusinessMemoryPolicy
from execution.business_operating_memory import (
    BusinessOperatingMemory,
    FileBusinessOperatingMemoryStore,
    project_business_memory_contract_bundle,
    project_business_memory_governance_summary,
)
from execution.business_operating_memory_types import BusinessMemoryRunRecord, PatternEvidence, SignalMemoryRecord
from execution.world_state_updater import WorldStateUpdate, WorldStateUpdater
from runtime._internal.effect_types import EffectActionType


def _run(run_id: str, *, completed: bool, goal_score: float, stop_reason: str = "execution_failed") -> BusinessMemoryRunRecord:
    return BusinessMemoryRunRecord(
        run_id=run_id,
        goal="grow pipeline",
        completed=completed,
        stop_reason=stop_reason,
        goal_score=goal_score,
        step_count=1,
        summary=f"run={run_id}",
        channel="headless",
        region="global",
        product_name="BusinesAIOS",
    )


def test_business_memory_compactor_derives_anti_patterns_and_trends() -> None:
    policy = BusinessMemoryPolicy(max_recent_runs=3, min_pattern_frequency=2)
    compactor = BusinessMemoryCompactor(policy=policy)
    memory = BusinessOperatingMemory(
        schema_version=2,
        tenant_id="tenant-1",
        business_id="biz-1",
        recent_runs=(
            _run("run-3", completed=False, goal_score=0.10),
            _run("run-2", completed=False, goal_score=0.20),
            _run("run-1", completed=True, goal_score=0.95, stop_reason="goal_reached"),
        ),
        recurring_failures=(
            PatternEvidence(
                key="timeout",
                count=2,
                confidence=0.60,
                frequency=0.66,
                freshness=0.90,
                last_seen_run_id="run-3",
                source_run_ids=("run-3", "run-2"),
            ),
        ),
        signal_memory=(SignalMemoryRecord(kind="demand", name="weekly", last_value="low", count=3),),
        total_runs=3,
        completed_runs=1,
        failed_runs=2,
        average_goal_score=0.42,
    )

    compacted, report = compactor.compact_with_report(memory)

    assert compacted.anti_patterns
    assert compacted.anti_patterns[0].key == "timeout"
    assert compacted.trends is not None
    assert compacted.trends.failure_trend in {"flat", "up", "down"}
    assert report.after_anti_patterns == 1


def test_business_memory_compactor_sanitizes_feedback_and_bounds_payload() -> None:
    policy = BusinessMemoryPolicy(
        approx_target_payload_bytes=400,
        approx_hard_payload_bytes=700,
        max_feedback_fields=3,
        max_recent_runs=12,
    )
    compactor = BusinessMemoryCompactor(policy=policy)
    huge_feedback = {f"key_{idx}": "x" * 400 for idx in range(10)}
    memory = BusinessOperatingMemory(
        schema_version=2,
        tenant_id="tenant-1",
        business_id="biz-1",
        recent_runs=tuple(_run(f"run-{idx}", completed=idx % 2 == 0, goal_score=0.2) for idx in range(20)),
        last_feedback=huge_feedback,
        total_runs=20,
        failed_runs=10,
        completed_runs=10,
    )

    compacted, report = compactor.compact_with_report(memory)

    assert len(compacted.last_feedback) <= 3
    assert len(compacted.recent_runs) <= 10
    assert report.trimmed_for_size_budget is True


def test_business_memory_policy_sanitizes_nested_feedback_without_second_brain_payload() -> None:
    policy = BusinessMemoryPolicy(max_feedback_fields=4, max_nested_depth=2)

    payload = policy.sanitize_feedback_payload(
        {
            "history": [{"ok": True, "meta": {"x": 1, "too": ["a", "b"]}}],
            "notes": {"text": "a" * 900},
            "decision_hint": {"next_action": "launch_campaign", "priority": 10},
            "empty": [],
        }
    )

    assert "history" in payload
    assert isinstance(payload["history"], list)
    assert payload["notes"]["text"].startswith("a")
    assert payload["decision_hint"] == {"priority": 10}
    assert "empty" not in payload


def test_business_memory_from_dict_migrates_malformed_payload_rows_fail_closed() -> None:
    policy = BusinessMemoryPolicy()
    memory = BusinessOperatingMemory.from_dict(
        {
            "tenant_id": "tenant-1",
            "business_id": "biz-1",
            "signal_memory": [{"name": "weekly", "count": "3"}, "bad-row"],
            "recent_runs": [{"run_id": "run-1", "goal": "grow", "completed": True, "goal_score": "0.8"}],
            "recurring_failures": ["timeout"],
            "last_feedback": {"nested": {"a": 1}},
        },
        policy=policy,
    )

    assert memory.signal_memory[0].count == 3
    assert memory.recent_runs[0].run_id == "run-1"
    assert memory.recurring_failures[0].key == "timeout"
    assert memory.last_feedback["nested"]["a"] == 1


def test_business_memory_store_replay_same_run_id_does_not_double_count_totals(tmp_path) -> None:
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "memory")

    store.remember_execution(
        tenant_id="tenant-1",
        business_id="biz-1",
        run_id="run-1",
        goal="grow pipeline",
        completed=False,
        stop_reason="execution_failed",
        final_feedback={"goal_score": 0.1, "error": "timeout"},
        step_count=1,
        profile={},
        constraints={},
        signals=[{"type": "lead_volume", "name": "weekly", "value": "low"}],
        meta={},
        channel="headless",
        region="eu",
        product_name="BusinesAIOS",
        recorded_at="2026-03-31T10:00:00Z",
    )
    after_replay = store.remember_execution(
        tenant_id="tenant-1",
        business_id="biz-1",
        run_id="run-1",
        goal="grow pipeline",
        completed=True,
        stop_reason="goal_reached",
        final_feedback={"goal_score": 0.9},
        step_count=2,
        profile={},
        constraints={},
        signals=[{"type": "lead_volume", "name": "weekly", "value": "high"}],
        meta={},
        channel="headless",
        region="eu",
        product_name="BusinesAIOS",
        recorded_at="2026-03-31T10:05:00Z",
    )

    assert after_replay.total_runs == 1
    assert after_replay.completed_runs == 1
    assert after_replay.failed_runs == 0
    assert after_replay.recent_runs[0].goal_score == 0.9


def test_business_memory_store_list_businesses_deduplicates(tmp_path) -> None:
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "memory")
    target = tmp_path / "memory" / "tenant-1"
    target.mkdir(parents=True)
    payload = {"tenant_id": "tenant-1", "business_id": "biz-1"}
    for name in ("a.json", "b.json"):
        (target / name).write_text(json.dumps(payload), encoding="utf-8")

    assert store.list_businesses(tenant_id="tenant-1") == (("tenant-1", "biz-1"),)


def test_world_state_updater_preserves_existing_meta_and_deduplicates_history() -> None:
    updater = WorldStateUpdater()
    update = updater.build_update(
        verification_result={
            "verified": True,
            "verification": {"status": "accepted", "external_refs": ["msg:1"], "source_of_truth": "router"},
        },
        action={"action_type": EffectActionType.TELEGRAM_SEND_MESSAGE, "action_id": "a1"},
    )
    state = {
        "meta": {
            "unrelated": {"keep": True},
            "execution_closed_loop": {
                "execution_history": [dict(update.meta_patch["execution_closed_loop"]["append_history"])],
            },
        }
    }

    result = updater.apply(world_state=state, update=update)
    loop_meta = result["meta"]["execution_closed_loop"]

    assert result["meta"]["unrelated"] == {"keep": True}
    assert len(loop_meta["execution_history"]) == 1
    assert loop_meta["recent_verified_runs"] == 1
    assert loop_meta["recent_actions"] == [EffectActionType.TELEGRAM_SEND_MESSAGE]


def test_world_state_updater_preserves_existing_loop_fields_when_patch_is_empty() -> None:
    updater = WorldStateUpdater()
    result = updater.apply(
        world_state={
            "meta": {
                "execution_closed_loop": {
                    "last_verification": {"verified": True},
                    "execution_history": [],
                    "custom": "keep",
                }
            }
        },
        update=WorldStateUpdate(updated_at="2026-04-01T00:00:00+00:00", meta_patch={}),
    )

    assert result["meta"]["execution_closed_loop"]["custom"] == "keep"
    assert result["meta"]["execution_closed_loop"]["last_verification"] == {"verified": True}


def test_business_memory_from_dict_dedupes_recent_runs_and_reconciles_counters() -> None:
    memory = BusinessOperatingMemory.from_dict(
        {
            "tenant_id": "tenant-1",
            "business_id": "biz-1",
            "recent_runs": [
                {"run_id": "run-1", "goal": "grow", "completed": True, "goal_score": 0.8},
                {"run_id": "run-1", "goal": "grow", "completed": False, "goal_score": 0.1},
                {"run_id": "run-2", "goal": "retain", "completed": False, "goal_score": 0.2},
            ],
            "total_runs": 1,
            "completed_runs": 2,
            "failed_runs": 2,
            "average_goal_score": 1.5,
        }
    )

    assert [row.run_id for row in memory.recent_runs] == ["run-1", "run-2"]
    assert memory.total_runs >= memory.completed_runs + memory.failed_runs
    assert 0.0 <= memory.average_goal_score <= 1.0


def test_business_memory_store_replay_same_signal_same_run_does_not_inflate_signal_count(tmp_path) -> None:
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "memory")

    first = store.remember_execution(
        tenant_id="tenant-1",
        business_id="biz-1",
        run_id="run-1",
        goal="grow pipeline",
        completed=False,
        stop_reason="execution_failed",
        final_feedback={"goal_score": 0.1, "error": "timeout"},
        step_count=1,
        profile={},
        constraints={},
        signals=[{"type": "lead_volume", "name": "weekly", "value": "low"}],
        meta={},
        channel="headless",
        region="eu",
        product_name="BusinesAIOS",
        recorded_at="2026-03-31T10:00:00Z",
    )
    second = store.remember_execution(
        tenant_id="tenant-1",
        business_id="biz-1",
        run_id="run-1",
        goal="grow pipeline",
        completed=False,
        stop_reason="execution_failed",
        final_feedback={"goal_score": 0.2, "error": "timeout"},
        step_count=2,
        profile={},
        constraints={},
        signals=[{"type": "lead_volume", "name": "weekly", "value": "mid"}],
        meta={},
        channel="headless",
        region="eu",
        product_name="BusinesAIOS",
        recorded_at="2026-03-31T10:05:00Z",
    )

    assert first.signal_memory[0].count == 1
    assert second.signal_memory[0].count == 1
    assert second.signal_memory[0].last_value == "mid"


def test_business_memory_store_replay_recalculates_pattern_frequency(tmp_path) -> None:
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "memory")

    store.remember_execution(
        tenant_id="tenant-1",
        business_id="biz-1",
        run_id="run-1",
        goal="grow pipeline",
        completed=False,
        stop_reason="execution_failed",
        final_feedback={"goal_score": 0.1, "error": "timeout"},
        step_count=1,
        profile={},
        constraints={},
        signals=[],
        meta={},
        channel="headless",
        region="eu",
        product_name="BusinesAIOS",
        recorded_at="2026-03-31T10:00:00Z",
    )
    store.remember_execution(
        tenant_id="tenant-1",
        business_id="biz-1",
        run_id="run-2",
        goal="grow pipeline",
        completed=False,
        stop_reason="execution_failed",
        final_feedback={"goal_score": 0.1, "error": "timeout"},
        step_count=1,
        profile={},
        constraints={},
        signals=[],
        meta={},
        channel="headless",
        region="eu",
        product_name="BusinesAIOS",
        recorded_at="2026-03-31T10:01:00Z",
    )
    memory = store.remember_execution(
        tenant_id="tenant-1",
        business_id="biz-1",
        run_id="run-1",
        goal="grow pipeline",
        completed=True,
        stop_reason="goal_reached",
        final_feedback={"goal_score": 0.9},
        step_count=2,
        profile={},
        constraints={},
        signals=[],
        meta={},
        channel="headless",
        region="eu",
        product_name="BusinesAIOS",
        recorded_at="2026-03-31T10:05:00Z",
    )

    assert memory.total_runs == 2
    assert memory.recurring_failures[0].count == 1
    assert memory.recurring_failures[0].frequency == 0.5


def test_world_state_updater_sanitizes_external_refs_and_keeps_distinct_history() -> None:
    updater = WorldStateUpdater()
    first = updater.build_update(
        verification_result={"verified": True, "verification": {"status": "accepted", "external_refs": ["msg:1", "msg:2"]}},
        action={"action_type": EffectActionType.TELEGRAM_SEND_MESSAGE, "action_id": "a1", "decision_id": "d1"},
    )
    second = updater.build_update(
        verification_result={"verified": True, "verification": {"status": "accepted", "external_refs": ["msg:1", "msg:2"]}},
        action={"action_type": EffectActionType.TELEGRAM_SEND_MESSAGE, "action_id": "a1", "decision_id": "d2"},
    )

    state = updater.apply(world_state={"meta": {}}, update=first)
    state = updater.apply(world_state=state, update=second)
    history = state["meta"]["execution_closed_loop"]["execution_history"]

    assert len(history) == 2
    assert history[0]["external_refs"] == ["msg:1", "msg:2"]


def test_business_memory_summary_and_state_adapter_use_canonical_evidence_projection(tmp_path) -> None:
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "memory")
    memory = store.remember_execution(
        tenant_id="tenant-1",
        business_id="biz-1",
        run_id="run-1",
        goal="grow demand",
        completed=True,
        stop_reason="goal_reached",
        final_feedback={"goal_score": 0.9, "next_action": "launch_campaign"},
        step_count=1,
        profile={"segment": "services", "channel": "seo"},
        constraints={"constraint_keys": "budget_cap", "next_action": "launch_campaign"},
        signals=[],
        meta={"region": "eu", "recommended_action": "route_lead"},
        channel="seo",
        region="eu",
        product_name="BusinesAIOS",
    )

    summary = memory.to_summary_payload()
    assert summary["learned_preferences"]["channel"] == "seo"
    assert summary["learned_preferences"]["region"] == "eu"

    from execution.business_memory_state_adapter import BusinessMemoryStateAdapter
    adapter = BusinessMemoryStateAdapter(store=store)
    context = adapter.to_state_context(memory.to_evidence_payload())

    assert context["evidence_only"] is True
    assert context["learned_preferences"]["channel"] == "seo"
    assert context["learned_preferences"]["region"] == "eu"
    assert "next_action" not in context["operating_constraints"]


def test_world_state_updater_sanitizes_last_verification_patch() -> None:
    updater = WorldStateUpdater()
    result = updater.apply(
        world_state={"meta": {"execution_closed_loop": {}}},
        update=WorldStateUpdate(
            updated_at="2026-04-01T00:00:00+00:00",
            meta_patch={
                "execution_closed_loop": {
                    "last_verification": {
                        "action_type": "send",
                        "verification_status": "verified",
                        "message": "x" * 500,
                        "external_refs": ["msg:1", "msg:2"],
                    }
                }
            },
        ),
    )

    last = result["meta"]["execution_closed_loop"]["last_verification"]
    assert len(last["message"]) == 256
    assert last["external_ref"] == "msg:1"
    assert last["external_refs"] == ["msg:1", "msg:2"]



def test_business_memory_state_projection_is_deterministic_under_reordered_input() -> None:
    left = BusinessOperatingMemory.from_dict(
        {
            "tenant_id": "tenant-1",
            "business_id": "biz-1",
            "learned_preferences": {"channel": "seo", "segment": "services"},
            "recurring_failures": [
                {"key": "timeout", "count": 2, "confidence": 0.7, "frequency": 0.5},
                {"key": "verification_failed", "count": 1, "confidence": 0.6, "frequency": 0.2},
            ],
            "anti_patterns": [{"key": "timeout", "confidence": 0.7, "frequency": 0.5}],
        }
    )
    right = BusinessOperatingMemory.from_dict(
        {
            "business_id": "biz-1",
            "tenant_id": "tenant-1",
            "recurring_failures": [
                {"key": "verification_failed", "count": 1, "confidence": 0.6, "frequency": 0.2},
                {"key": "timeout", "count": 2, "confidence": 0.7, "frequency": 0.5},
            ],
            "anti_patterns": [{"frequency": 0.5, "key": "timeout", "confidence": 0.7}],
            "learned_preferences": {"segment": "services", "channel": "seo"},
        }
    )

    assert left.to_state_context_payload() == right.to_state_context_payload()


def test_business_memory_policy_bounds_deep_nested_feedback_deterministically() -> None:
    policy = BusinessMemoryPolicy(max_nested_depth=2, max_nested_mapping_items=2, max_nested_sequence_items=2)
    payload = policy.sanitize_feedback_payload(
        {
            "evidence": {
                "a": {"x": 1, "y": 2, "z": {"overflow": True}},
                "b": [1, 2, 3],
                "c": "drop-by-limit",
            }
        }
    )

    assert payload == {"evidence": {"a": {"x": 1, "y": 2}, "b": [1, 2]}}


def test_canonicalize_business_memory_payload_uses_profile_fallback_and_strips_guidance() -> None:
    from execution.business_operating_memory import canonicalize_business_memory_payload

    memory = canonicalize_business_memory_payload(
        {
            "tenant_id": "tenant-1",
            "business_id": "biz-1",
            "profile": {"segment": "services", "region": "eu"},
            "last_feedback": {"decision_hint": {"next_action": "launch_campaign", "priority": 5}},
            "recurring_failures": [{"action": "timeout", "count": 2, "confidence": 0.8}],
        }
    )

    assert memory.business_profile == {"region": "eu", "segment": "services"}
    assert memory.last_feedback["decision_hint"] == {"priority": 5}
    assert memory.recurring_failures[0].key == "timeout"


def test_project_business_memory_state_context_is_deterministic_for_reordered_input() -> None:
    from execution.business_operating_memory import project_business_memory_state_context

    left = project_business_memory_state_context(
        {
            "tenant_id": "tenant-1",
            "business_id": "biz-1",
            "recurring_failures": [
                {"key": "timeout", "count": 2, "confidence": 0.8, "frequency": 0.4},
                {"key": "quota", "count": 5, "confidence": 0.7, "frequency": 0.6},
            ],
            "profile": {"segment": "services"},
        }
    )
    right = project_business_memory_state_context(
        {
            "business_id": "biz-1",
            "tenant_id": "tenant-1",
            "profile": {"segment": "services"},
            "recurring_failures": [
                {"key": "quota", "count": 5, "confidence": 0.7, "frequency": 0.6},
                {"key": "timeout", "count": 2, "confidence": 0.8, "frequency": 0.4},
            ],
        }
    )

    assert left == right


def test_business_memory_projection_helpers_are_deterministic_and_profile_aware() -> None:
    from execution.business_operating_memory import (
        project_business_memory_profile,
        project_business_memory_recent_runs,
        project_business_memory_summary,
    )

    payload = {
        'profile': {'segment': 'services'},
        'recent_runs': [
            {'run_id': 'run-2', 'goal': 'grow', 'completed': False, 'goal_score': 0.1},
            {'run_id': 'run-1', 'goal': 'grow', 'completed': True, 'goal_score': 0.9},
        ],
        'last_feedback': {'decision_hint': {'next_action': 'launch_campaign', 'priority': 2}},
    }

    assert project_business_memory_profile(payload) == {'segment': 'services'}
    assert project_business_memory_recent_runs(payload, limit=1)[0]['run_id'] == 'run-2'
    first = project_business_memory_summary(payload)
    second = project_business_memory_summary(dict(reversed(list(payload.items()))))
    assert first == second


def test_autonomy_memory_step_finalize_feedback_sanitizes_business_memory_without_dropping_runtime_fields() -> None:
    from application.autonomy.autonomy_memory_step import AutonomyMemoryStep

    final_feedback = AutonomyMemoryStep.finalize_feedback(
        previous_feedback={},
        business_memory_context={
            'profile': {'segment': 'services'},
            'recent_external_refs': ['listing-42'],
            'blocked_actions': ['ACTION_SEND_EMAIL'],
            'last_feedback': {'decision_hint': {'next_action': 'launch_campaign', 'priority': 4}},
        },
        goal_plan_context={},
        performance_context={},
        adaptive_optimization_context={},
        multi_goal_context={},
        owner_path_context={},
        steps=(),
    )

    assert final_feedback['business_memory']['profile'] == {'segment': 'services'}
    assert final_feedback['business_memory']['recent_external_refs'] == ['listing-42']
    assert 'blocked_actions' not in final_feedback['business_memory']
    assert final_feedback['business_memory']['last_feedback']['decision_hint'] == {'priority': 4}


def test_business_memory_state_adapter_inject_context_sets_canonical_memory_and_evidence() -> None:
    from core.ai.world_state import WorldStateV1
    from execution.business_memory_state_adapter import BusinessMemoryStateAdapter

    adapter = BusinessMemoryStateAdapter()
    world_state = WorldStateV1(schema_version=1, user={}, session={}, product={}, economy={}, timestamp_ms=1, tenant_id='tenant-1', meta={})
    updated = adapter.inject_context(
        world_state=world_state,
        memory_context={
            'profile': {'segment': 'services'},
            'last_feedback': {'decision_hint': {'next_action': 'launch_campaign', 'priority': 2}},
            'recurring_failures': [{'action': 'timeout', 'count': 2, 'confidence': 0.8}],
        },
    )

    assert updated.meta['business_memory']['business_profile'] == {'segment': 'services'}
    assert updated.meta['business_memory']['last_feedback']['decision_hint'] == {'priority': 2}
    assert updated.meta['business_memory_evidence']['aggregated_business_profile'] == {'segment': 'services'}
    assert updated.meta['business_memory_evidence']['recurring_failures'][0]['action'] == 'timeout'


def test_business_memory_query_recurring_pattern_surfaces_use_canonical_state_projection(tmp_path) -> None:
    from execution.business_memory_query import BusinessMemoryQueryService

    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / 'memory')
    store.remember_execution(
        tenant_id='tenant-1',
        business_id='biz-1',
        run_id='run-1',
        goal='grow demand',
        completed=False,
        stop_reason='execution_failed',
        final_feedback={'goal_score': 0.1, 'error': 'timeout_external'},
        step_count=1,
        profile={},
        constraints={},
        signals=[],
        meta={},
        channel='headless',
        region='eu',
        product_name='BusinesAIOS',
        recorded_at='2026-04-01T00:00:00Z',
    )

    query = BusinessMemoryQueryService(store=store)
    failures = query.get_recurring_failures(tenant_id='tenant-1', business_id='biz-1')

    assert failures
    assert failures[0]['key']
    assert failures[0]['action'] == failures[0]['key']


def test_headless_feedback_reader_uses_canonical_business_memory_before_step() -> None:
    from types import SimpleNamespace

    from application.headless.feedback import SimpleHeadlessFeedbackReader
    from execution.headless_contract import GoalExecutionRequest

    request = GoalExecutionRequest(
        goal='grow demand',
        business_id='biz-1',
        tenant_id='tenant-1',
        meta={'business_memory': {'profile': {'segment': 'services'}, 'blocked_actions': ['ACTION_SEND_EMAIL']}},
    )
    reader = SimpleHeadlessFeedbackReader.default()
    envelope = SimpleNamespace(decision=SimpleNamespace(decision_id='d1', action='ACTION_CREATE_LISTING', payload={}, correlation_id='c1'))
    executable_action = SimpleNamespace(action_id='a1', action_type='ACTION_CREATE_LISTING')
    action_result = SimpleNamespace(payload={'effector': {'verified': True, 'status': 'verified', 'external_ref': 'ref-1', 'evidence': {'external_refs': ['ref-1']}}}, attempted=True, executed=True, verified=True, operator_required=False, status='ok')
    result = SimpleNamespace(output={'terminal': True, 'converted': True, 'external_ref': 'ref-1'}, error=None)

    feedback = reader.read(
        request=request,
        state=None,
        envelope=envelope,
        executable_action=executable_action,
        action_result=action_result,
        result=result,
        step_index=0,
    )

    assert feedback['business_memory_before_step']['business_profile'] == {'segment': 'services'}
    assert 'blocked_actions' not in feedback['business_memory_before_step']


def test_business_memory_contract_bundle_is_deterministic_and_bounded() -> None:
    from execution.business_operating_memory import project_business_memory_contract_bundle

    payload = {
        "profile": {"segment": "services"},
        "active_goals": ["grow", "grow", "retain"],
        "recent_runs": [
            {"run_id": f"run-{idx}", "goal": "grow", "completed": idx % 2 == 0, "goal_score": 0.9 if idx % 2 == 0 else 0.1}
            for idx in range(40)
        ],
        "last_feedback": {
            "decision_hint": {"next_action": "launch_campaign", "priority": 2},
            "notes": [str(idx) for idx in range(30)],
        },
        "recurring_failures": [{"action": "timeout", "count": 3, "confidence": 0.8}],
    }

    first = project_business_memory_contract_bundle(payload, recent_runs_limit=50)
    second = project_business_memory_contract_bundle(dict(reversed(list(payload.items()))), recent_runs_limit=50)

    assert first == second
    assert len(first["recent_runs"]) <= 20
    assert first["summary"]["active_goals"] == ["grow", "retain"]
    assert first["evidence"]["last_feedback"]["decision_hint"] == {"priority": 2}


def test_business_memory_state_adapter_inject_context_sets_summary_without_drift() -> None:
    from core.ai.world_state import WorldStateV1
    from execution.business_memory_state_adapter import BusinessMemoryStateAdapter

    adapter = BusinessMemoryStateAdapter()
    world_state = WorldStateV1(schema_version=1, user={}, session={}, product={}, economy={}, timestamp_ms=1, tenant_id='tenant-1', meta={})
    updated = adapter.inject_context(
        world_state=world_state,
        memory_context={
            'profile': {'segment': 'services'},
            'active_goals': ['grow demand'],
            'blocked_actions': ['ACTION_SEND_EMAIL'],
            'recurring_failures': [{'action': 'timeout', 'count': 2, 'confidence': 0.8}],
        },
    )

    assert updated.meta['business_memory_summary']['business_profile'] == {'segment': 'services'}
    assert updated.meta['business_memory_summary']['active_goals'] == ['grow demand']
    assert 'blocked_actions' not in updated.meta['business_memory_summary']



def test_business_memory_contract_bundle_is_deterministic_for_reordered_payload() -> None:
    left = {
        "tenant_id": "tenant-1",
        "business_id": "biz-1",
        "profile": {"segment": "services", "region": "eu"},
        "active_goals": ["grow", "retain", "grow"],
        "recurring_failures": [
            {"action": "timeout", "count": 2, "confidence": 0.7, "frequency": 0.5, "freshness": 0.9},
            {"key": "low_conversion", "count": 1, "confidence": 0.4, "frequency": 0.2, "freshness": 0.5},
        ],
        "recent_runs": [
            {"run_id": "run-2", "goal": "retain", "completed": False, "goal_score": 0.2},
            {"run_id": "run-1", "goal": "grow", "completed": True, "goal_score": 0.9},
        ],
    }
    right = {
        "business_id": "biz-1",
        "tenant_id": "tenant-1",
        "profile": {"region": "eu", "segment": "services"},
        "active_goals": ["retain", "grow"],
        "recent_runs": [
            {"run_id": "run-2", "goal": "retain", "completed": False, "goal_score": 0.2},
            {"run_id": "run-1", "goal": "grow", "completed": True, "goal_score": 0.9},
        ],
        "recurring_failures": [
            {"key": "low_conversion", "count": 1, "confidence": 0.4, "frequency": 0.2, "freshness": 0.5},
            {"action": "timeout", "count": 2, "confidence": 0.7, "frequency": 0.5, "freshness": 0.9},
        ],
    }

    left_bundle = project_business_memory_contract_bundle(left)
    right_bundle = project_business_memory_contract_bundle(right)

    assert left_bundle["governance_summary"] == right_bundle["governance_summary"]
    assert left_bundle["state_context"] == right_bundle["state_context"]


def test_business_memory_governance_summary_is_bounded_and_canonical() -> None:
    summary = project_business_memory_governance_summary(
        {
            "tenant_id": "tenant-1",
            "business_id": "biz-1",
            "business_profile": {f"k{i}": f"v{i}" for i in range(80)},
            "active_goals": [f"goal-{i}" for i in range(20)],
            "recurring_failures": [f"failure-{i}" for i in range(30)],
            "recurring_wins": [f"win-{i}" for i in range(30)],
            "anti_patterns": [f"anti-{i}" for i in range(30)],
            "average_goal_score": 2.0,
        },
        policy=BusinessMemoryPolicy(max_profile_fields=5, max_active_goals=3, max_failures=4, max_wins=4, max_anti_patterns=4),
    )
    assert len(summary["business_profile"]) <= 5
    assert len(summary["active_goals"]) == 3
    assert len(summary["recurring_failures"]) == 4
    assert len(summary["recurring_wins"]) == 4
    assert len(summary["anti_patterns"]) == 4
    assert 0.0 <= summary["average_goal_score"] <= 1.0


def test_business_memory_store_save_load_is_stable_across_repeated_roundtrips(tmp_path) -> None:
    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "memory")
    payload = {
        "tenant_id": "tenant-1",
        "business_id": "biz-1",
        "profile": {"segment": "services"},
        "active_goals": ["grow", "retain"],
        "last_feedback": {"nested": {"priority": 1, "next_action": "send_email"}},
        "recent_runs": [
            {"run_id": "run-1", "goal": "grow", "completed": True, "goal_score": 0.9},
            {"run_id": "run-2", "goal": "retain", "completed": False, "goal_score": 0.2},
        ],
    }
    memory = BusinessOperatingMemory.from_dict(payload)
    store.save(memory)
    first = store.load(tenant_id="tenant-1", business_id="biz-1").to_dict()
    store.save(BusinessOperatingMemory.from_dict(first))
    second = store.load(tenant_id="tenant-1", business_id="biz-1").to_dict()
    assert first == second


def test_business_memory_feedback_snapshot_is_deterministic_and_evidence_only() -> None:
    from execution.business_operating_memory import project_business_memory_feedback_snapshot

    left = {
        "tenant_id": "tenant-1",
        "business_id": "biz-1",
        "profile": {"segment": "services", "region": "eu"},
        "active_goals": ["retain", "grow"],
        "recent_runs": [
            {"run_id": "run-2", "goal": "retain", "completed": False, "goal_score": 0.2},
            {"run_id": "run-1", "goal": "grow", "completed": True, "goal_score": 0.9},
        ],
        "last_feedback": {"recent_external_refs": ["ref-2", "ref-1"], "next_action": "launch"},
    }
    right = {
        "business_id": "biz-1",
        "tenant_id": "tenant-1",
        "business_profile": {"region": "eu", "segment": "services"},
        "active_goals": ["grow", "retain"],
        "recent_runs": [
            {"run_id": "run-2", "goal": "retain", "completed": False, "goal_score": 0.2},
            {"run_id": "run-1", "goal": "grow", "completed": True, "goal_score": 0.9},
        ],
        "last_feedback": {"recent_external_refs": ["ref-1", "ref-2"], "blocked_actions": ["launch"]},
    }

    first = project_business_memory_feedback_snapshot(left)
    second = project_business_memory_feedback_snapshot(right)

    assert first == second
    assert first["business_profile"] == {"region": "eu", "segment": "services"}
    assert first["active_goals"] == ["grow", "retain"]
    assert "blocked_actions" not in first
    assert first["evidence_only"] is True
    assert first["must_not_issue_decision"] is True


def test_owner_path_state_synthesis_accepts_canonical_business_memory_summary(tmp_path) -> None:
    from execution.owner_path.owner_path_service import FileOwnerPathStore, OwnerPathService

    service = OwnerPathService(store=FileOwnerPathStore(root_dir=tmp_path / "owner-path"))
    owner_path = service.update_after_step(
        tenant_id="tenant-1",
        business_id="biz-1",
        goal="grow demand",
        feedback={
            "business_memory_summary": {
                "tenant_id": "tenant-1",
                "business_id": "biz-1",
                "business_profile": {"segment": "services"},
                "active_goals": ["grow demand"],
                "next_action": "launch",
            },
            "decision_id": "dec-1",
            "correlation_id": "corr-1",
        },
    )

    assert owner_path["stages"]["state_synthesis"]["present"] is True
    assert owner_path["stages"]["state_synthesis"]["reason"] == "business_memory_summary"


def test_autonomy_loop_persists_canonical_business_memory_summary_after_step(tmp_path) -> None:
    from tests.e2e._headless_harness import ScenarioStep, build_harness, make_request

    harness = build_harness(tmp_path, scenario=[ScenarioStep(action_type="email_send", output={"terminal": True, "goal_reached": True})])
    report = harness.run(make_request(goal="grow demand"))

    summary = dict(report.final_feedback.get("business_memory_summary") or {})
    after_step = dict(report.final_feedback.get("business_memory_after_step") or {})

    assert summary.get("evidence_only") is True
    assert summary.get("must_not_issue_decision") is True
    assert summary.get("must_not_unlock_effects") is True
    assert summary.get("business_id") == after_step.get("business_id")


def test_business_memory_meta_payloads_are_deterministic_and_canonical() -> None:
    from execution.business_operating_memory import project_business_memory_meta_payloads

    left = {
        "tenant_id": "tenant-1",
        "business_id": "biz-1",
        "business_profile": {"segment": "services", "region": "eu"},
        "active_goals": ["grow demand", "grow demand", "retain users"],
        "recurring_failures": [{"key": "timeout", "count": 3, "frequency": 0.6, "confidence": 0.8}],
        "anti_patterns": [{"key": "overpromising", "confidence": 0.7, "frequency": 0.4, "freshness": 0.6}],
        "last_feedback": {"next_action": "email 100 leads", "notes": {"recommended_action": "do it now", "safe": "keep"}},
    }
    right = {key: left[key] for key in reversed(list(left.keys()))}

    first = project_business_memory_meta_payloads(left, recent_runs_limit=50)
    second = project_business_memory_meta_payloads(right, recent_runs_limit=50)

    assert first == second
    assert first["business_memory"]["business_profile"] == {"region": "eu", "segment": "services"}
    assert first["business_memory_summary"]["active_goals"] == ["grow demand", "retain users"]
    assert "next_action" not in first["business_memory"]["last_feedback"]
    assert "recommended_action" not in first["business_memory"]["last_feedback"]["notes"]
    assert first["business_memory_evidence"]["aggregated_business_profile"] == {"region": "eu", "segment": "services"}


def test_business_memory_replay_remains_counter_and_pattern_stable(tmp_path) -> None:
    from execution.business_operating_memory import FileBusinessOperatingMemoryStore

    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path)
    common = dict(
        tenant_id="tenant-1",
        business_id="biz-1",
        run_id="run-1",
        goal="grow demand",
        step_count=3,
        profile={"segment": "services"},
        constraints={"channel": "seo"},
        signals=[{"kind": "channel", "name": "seo", "value": "good", "count": 1}],
        meta={"channel": "seo"},
        channel="seo",
        region="eu",
        product_name="core",
        recorded_at="2026-03-31T00:00:00Z",
    )

    first = store.remember_execution(
        completed=False,
        stop_reason="timeout",
        final_feedback={"failure_kind": "timeout", "next_action": "retry later"},
        **common,
    )
    second = store.remember_execution(
        completed=False,
        stop_reason="timeout",
        final_feedback={"failure_kind": "timeout", "recommended_action": "retry again"},
        **common,
    )

    assert first.total_runs == 1
    assert second.total_runs == 1
    assert second.failed_runs == 1
    assert second.completed_runs == 0
    assert len(second.recent_runs) == 1
    assert [item.key for item in second.recurring_failures] == ["timeout"]
    assert second.recurring_failures[0].count == 1
    assert second.signal_memory[0].count == 1
    assert "recommended_action" not in second.last_feedback



def test_business_memory_contract_bundle_is_deterministic_across_pattern_permutations() -> None:
    from itertools import permutations

    base_patterns = [
        {"action": "timeout", "count": 2, "confidence": 0.8, "frequency": 0.4},
        {"action": "quota", "count": 5, "confidence": 0.7, "frequency": 0.6},
        {"action": "verification_failed", "count": 1, "confidence": 0.65, "frequency": 0.2},
    ]
    expected = None
    for ordering in permutations(base_patterns):
        bundle = project_business_memory_contract_bundle(
            {
                "tenant_id": "tenant-1",
                "business_id": "biz-1",
                "profile": {"segment": "services", "region": "eu"},
                "active_goals": ["grow pipeline", "grow pipeline"],
                "recurring_failures": list(ordering),
                "last_feedback": {"decision_hint": {"next_action": "launch_campaign", "priority": 4}},
            }
        )
        current = {
            "evidence": bundle["evidence"],
            "summary": bundle["summary"],
            "governance_summary": bundle["governance_summary"],
            "patterns": bundle["patterns"],
            "state_context": bundle["state_context"],
        }
        if expected is None:
            expected = current
        else:
            assert current == expected



def test_business_memory_meta_payloads_are_replay_stable_for_same_run_id(tmp_path) -> None:
    from execution.business_operating_memory import project_business_memory_meta_payloads

    store = FileBusinessOperatingMemoryStore(root_dir=tmp_path / "memory")
    observed = []
    for payload in (
        {"goal_score": 0.1, "error": "timeout", "decision_hint": {"next_action": "launch_campaign"}},
        {"goal_score": 0.9, "goal_reached": True, "recommended_action": "raise_budget"},
        {"goal_score": 0.9, "goal_reached": True, "blocked_actions": ["SEND_EMAIL"]},
    ):
        memory = store.remember_execution(
            tenant_id="tenant-1",
            business_id="biz-1",
            run_id="run-1",
            goal="grow pipeline",
            completed=bool(payload.get("goal_reached")),
            stop_reason="goal_reached" if payload.get("goal_reached") else "execution_failed",
            final_feedback=payload,
            step_count=1,
            profile={"segment": "services"},
            constraints={"budget": "tight", "next_action": "launch_campaign"},
            signals=[{"type": "lead_volume", "name": "weekly", "value": "mid"}],
            meta={"recommended_action": "raise_budget", "region": "eu"},
            channel="headless",
            region="eu",
            product_name="BusinesAIOS",
        )
        observed.append(project_business_memory_meta_payloads(memory.to_dict()))

    assert observed[-1]["business_memory"]["business_profile"] == {"region": "eu", "segment": "services"}
    assert observed[-1]["business_memory_summary"]["total_runs"] == 1
    assert observed[-1]["business_memory_summary"]["completed_runs"] == 1
    assert observed[-1]["business_memory_summary"]["failed_runs"] == 0
    assert observed[-1]["business_memory_evidence"]["aggregated_business_profile"] == {"region": "eu", "segment": "services"}
    assert "next_action" not in observed[-1]["business_memory"]["last_feedback"]
    assert "blocked_actions" not in observed[-1]["business_memory"]



def test_business_memory_policy_large_nested_payload_is_bounded_and_deterministic() -> None:
    policy = BusinessMemoryPolicy(
        max_feedback_fields=4,
        max_nested_depth=2,
        max_nested_mapping_items=3,
        max_nested_sequence_items=2,
        max_summary_length=32,
    )
    raw = {
        "outer": {
            "alpha": {"x": "a" * 100, "y": "b" * 100, "z": "c" * 100, "overflow": "drop"},
            "beta": [1, 2, 3, 4],
            "decision_hint": {"next_action": "launch_campaign", "priority": 9},
            "blocked_actions": ["SEND_EMAIL"],
        },
        "notes": ["x" * 100, "y" * 100, "z" * 100],
        "noise": {str(i): i for i in range(10)},
    }
    first = policy.sanitize_feedback_payload(raw)
    second = policy.sanitize_feedback_payload(dict(reversed(list(raw.items()))))
    assert first == second
    assert len(first) <= 4
    assert "blocked_actions" not in first.get("outer", {})
    assert first["outer"]["decision_hint"] == {"priority": 9}
    assert len(first["notes"]) == 2
