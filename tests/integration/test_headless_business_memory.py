from __future__ import annotations

from dataclasses import dataclass

from core.ai.decision import Decision, DecisionEnvelope
from application.effects.effect_journal import FileEffectJournal
from execution.goal_score import GoalScoreEngine
from execution.headless_contract import GoalExecutionRequest, HeadlessExecutionContract
from application.headless.feedback import SimpleHeadlessFeedbackReader
from application.headless.goal_mapper import HeadlessGoalStateMapper
from execution.headless_ledger import FileHeadlessLedger
from execution.headless_state_store import FileHeadlessStateStore
from application.headless.stop_policy import HeadlessStopPolicy
from execution.idempotency_guard import FileIdempotencyGuard
from execution.outcome_normalizer import OutcomeNormalizer
from execution.policy_explainer import PolicyExplainer
from application.learning.retry_taxonomy import RetryTaxonomy
from runtime.execution.executor_result import ExecutionResult
from runtime.platform.business_memory.service import BusinessMemoryService
from runtime.platform.business_memory.store import FileBusinessMemoryStore


@dataclass
class StubDecisionCore:
    def optimize(self, state):
        return DecisionEnvelope(
            decision=Decision(
                decision_id='dec-memory',
                issuer_id='businesaios-core',
                issued_at_ms=1,
                expires_at_ms=2,
                policy_id='policy-88',
                action='ACTION_CREATE_LISTING',
                payload={'feedback_seed': {'terminal': True}},
                snapshot_id='snap-1',
                state_hash='hash-1',
                correlation_id='corr-memory',
                state_schema_version=1,
                action_schema_version=1,
            ),
            payload_hash='hash',
            signature='sig',
            kid='kid',
        )


@dataclass
class StubExecutor:
    def execute(self, env):
        return ExecutionResult(
            ok=True,
            output={
                'converted': True,
                'terminal': True,
                'effector': {
                    'verified': True,
                    'status': 'verified',
                    'external_ref': 'listing-42',
                    'evidence': {'external_refs': ['listing-42']},
                },
                'external_ref': 'listing-42',
            },
            error=None,
            decision_id=env.decision.decision_id,
            correlation_id=env.decision.correlation_id,
        )


def test_headless_contract_updates_business_memory_after_verified_outcome(tmp_path) -> None:
    memory_service = BusinessMemoryService(store=FileBusinessMemoryStore(root_dir=tmp_path / 'memory'))
    contract = HeadlessExecutionContract(
        decision_core=StubDecisionCore(),
        executor=StubExecutor(),
        state_mapper=HeadlessGoalStateMapper(),
        feedback_reader=SimpleHeadlessFeedbackReader(),
        stop_policy=HeadlessStopPolicy(max_failures=1),
        ledger=FileHeadlessLedger(root_dir=tmp_path / 'ledger'),
        state_store=FileHeadlessStateStore(root_dir=tmp_path / 'state'),
        effect_journal=FileEffectJournal(root_dir=tmp_path / 'effects'),
        idempotency_guard=FileIdempotencyGuard(root_dir=tmp_path / 'idem'),
        goal_score_engine=GoalScoreEngine(),
        retry_taxonomy=RetryTaxonomy(),
        policy_explainer=PolicyExplainer(),
        outcome_normalizer=OutcomeNormalizer(),
        business_memory_service=memory_service,
    )

    report = contract.execute_autopilot(
        GoalExecutionRequest(
            goal='publish service page',
            business_id='biz-1',
            tenant_id='tenant-1',
            profile={'segment': 'services'},
            max_steps=1,
        )
    )

    assert report.steps[0].verified is True
    assert report.final_feedback['business_memory']['recent_external_refs'][0] == 'listing-42'
    persisted = memory_service.get(business_id='biz-1')
    assert persisted['last_verified_outcomes'][0]['external_refs'] == ['listing-42']



def test_headless_goal_mapper_strips_second_brain_guidance_from_request_meta() -> None:
    mapper = HeadlessGoalStateMapper()
    state = mapper.to_world_state(
        request=GoalExecutionRequest(
            goal='grow demand',
            business_id='biz-1',
            tenant_id='tenant-1',
            meta={
                'business_memory': {
                    'blocked_actions': ['ACTION_SEND_EMAIL'],
                    'learned_preferences': {'channel': 'seo', 'recommended_action': 'launch_campaign'},
                }
            },
        ),
        step_index=0,
        previous_feedback={},
    )

    assert 'blocked_actions' not in state.meta['business_memory']
    assert state.meta['business_memory']['learned_preferences'] == {'channel': 'seo'}
    assert state.meta['business_memory_evidence']['learned_preferences'] == {'channel': 'seo'}


def test_headless_goal_mapper_rehydrates_profile_based_business_memory_without_second_brain_guidance() -> None:
    mapper = HeadlessGoalStateMapper()
    state = mapper.to_world_state(
        request=GoalExecutionRequest(
            goal='grow demand',
            business_id='biz-2',
            tenant_id='tenant-2',
            meta={
                'business_memory': {
                    'profile': {'segment': 'services'},
                    'last_feedback': {'decision_hint': {'next_action': 'launch_campaign', 'priority': 1}},
                    'recurring_failures': [{'action': 'timeout', 'count': 2, 'confidence': 0.8}],
                }
            },
        ),
        step_index=0,
        previous_feedback={},
    )

    assert state.meta['business_memory']['business_profile'] == {'segment': 'services'}
    assert state.meta['business_memory']['last_feedback']['decision_hint'] == {'priority': 1}
    assert state.meta['business_memory_evidence']['aggregated_business_profile'] == {'segment': 'services'}
    assert state.meta['business_memory_evidence']['recurring_failures'][0]['key'] == 'timeout'


def test_autonomy_state_assembly_merges_business_profile_into_request_profile_without_second_brain_guidance() -> None:
    from types import SimpleNamespace
    from application.autonomy.autonomy_state_assembly import AutonomyStateAssembly

    request = GoalExecutionRequest(
        goal='grow demand',
        business_id='biz-3',
        tenant_id='tenant-3',
        profile={'region': 'eu'},
        meta={},
    )
    enriched = AutonomyStateAssembly.enrich_request_with_business_memory(
        request=request,
        business_memory_context={
            'business_profile': {'segment': 'services', 'region': 'na'},
            'last_feedback': {'nested': {'next_action': 'launch_campaign', 'priority': 3}},
        },
    )

    assert enriched.profile == {'segment': 'services', 'region': 'eu'}
    assert enriched.meta['business_memory']['last_feedback']['nested'] == {'priority': 3}


def test_headless_goal_mapper_merges_memory_profile_into_meta_profile() -> None:
    mapper = HeadlessGoalStateMapper()
    state = mapper.to_world_state(
        request=GoalExecutionRequest(
            goal='grow demand',
            business_id='biz-4',
            tenant_id='tenant-4',
            profile={'region': 'eu'},
            meta={'business_memory': {'business_profile': {'segment': 'services', 'region': 'na'}}},
        ),
        step_index=0,
        previous_feedback={},
    )

    assert state.meta['profile'] == {'segment': 'services', 'region': 'eu'}


def test_state_assembly_snapshot_uses_canonical_business_memory_projection(tmp_path) -> None:
    from application.autonomy.autonomy_state_assembly import AutonomyStateAssembly
    from execution.headless_contract import GoalExecutionRequest
    from application.headless.goal_mapper import HeadlessGoalStateMapper
    from execution.headless_state_store import FileHeadlessStateStore

    class DummyContract:
        def __init__(self, root):
            self._state_store = FileHeadlessStateStore(root_dir=root / 'state')
            self._business_memory_state_adapter = None
            self._capability_health_registry = None
            self._capability_health_scoring_service = None
            self._state_mapper = HeadlessGoalStateMapper()

    class DummyTrace:
        run_id = 'run-snapshot'
        def record(self, **kwargs):
            return None

    request = GoalExecutionRequest(
        goal='grow demand',
        business_id='biz-1',
        tenant_id='tenant-1',
        meta={'business_memory': {'profile': {'segment': 'services'}, 'last_feedback': {'decision_hint': {'next_action': 'launch_campaign', 'priority': 1}}}},
    )
    assembly = AutonomyStateAssembly(contract=DummyContract(tmp_path))
    assembly.assemble_state(
        request=request,
        trace=DummyTrace(),
        step_index=0,
        previous_feedback={},
        business_memory_context=dict(request.meta.get('business_memory') or {}),
    )
    snap = assembly._contract._state_store.load_latest_snapshot(run_id='run-snapshot')
    assert snap['business_memory']['business_profile'] == {'segment': 'services'}
    assert snap['business_memory']['last_feedback']['decision_hint'] == {'priority': 1}
