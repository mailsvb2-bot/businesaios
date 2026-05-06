from growth.core import (
    GrowthCycle,
    GrowthEngine,
    GrowthMemory,
    GrowthPlanBuilder,
    GrowthStateTransition,
    OpportunityDetector,
    OpportunityRanker,
    RevenueFeedbackLoop,
    StateSnapshot,
)
from growth.core.growth_cycle import GrowthCycle as LegacyGrowthCycle
from growth.core.growth_memory import GrowthMemory as LegacyGrowthMemory
from growth.core.growth_plan_builder import GrowthPlanBuilder as LegacyGrowthPlanBuilder
from growth.core.growth_state_transition import GrowthStateTransition as LegacyGrowthStateTransition
from growth.core.opportunity_detector import OpportunityDetector as LegacyOpportunityDetector
from growth.core.opportunity_ranker import OpportunityRanker as LegacyOpportunityRanker
from growth.core.revenue_feedback_loop import RevenueFeedbackLoop as LegacyRevenueFeedbackLoop
from growth.core.state_snapshot import StateSnapshot as LegacyStateSnapshot


def test_growth_core_public_api_exports_collapsed_surfaces() -> None:
    assert GrowthEngine.__name__ == 'GrowthEngine'
    assert GrowthCycle.__name__ == 'GrowthCycle'
    assert GrowthMemory.__name__ == 'GrowthMemory'
    assert GrowthPlanBuilder.__name__ == 'GrowthPlanBuilder'
    assert GrowthStateTransition.__name__ == 'GrowthStateTransition'
    assert OpportunityDetector.__name__ == 'OpportunityDetector'
    assert OpportunityRanker.__name__ == 'OpportunityRanker'
    assert RevenueFeedbackLoop.__name__ == 'RevenueFeedbackLoop'
    assert StateSnapshot.__name__ == 'StateSnapshot'


def test_growth_engine_provides_core_orchestration_helpers() -> None:
    engine = GrowthEngine()
    signals = [
        {'channel': 'ads', 'score': 0.4},
        {'channel': 'organic', 'intent_score': 0.8},
        {'channel': 'email', 'score': 0.0},
    ]
    detected = engine.detect_opportunities(signals)
    ranked = engine.rank_opportunities(detected)
    summary = engine.build_opportunity_summary(ranked)
    cycle = engine.start_cycle('cycle-1')
    snapshot = engine.snapshot_state('biz-1', {'stage': 'active'})
    transition = engine.next_state('draft', 'launch')
    feedback = engine.apply_revenue_feedback({'status': 'accepted'}, 12.5)
    engine.remember_event({'type': 'launch'})

    assert [item['channel'] for item in detected] == ['ads', 'organic']
    assert [item['channel'] for item in ranked] == ['organic', 'ads']
    assert summary == {'count': 2, 'channels': ['organic', 'ads']}
    assert cycle == GrowthCycle(cycle_id='cycle-1', objective=cycle.objective)
    assert snapshot == StateSnapshot(business_id='biz-1', values={'stage': 'active'})
    assert transition == 'draft->launch'
    assert feedback == {'action_result': {'status': 'accepted'}, 'revenue_delta': 12.5}
    assert engine.memory_events() == [{'type': 'launch'}]


def test_legacy_growth_core_imports_stay_compatible() -> None:
    assert LegacyGrowthCycle is GrowthCycle
    assert LegacyGrowthMemory is GrowthMemory
    assert LegacyGrowthPlanBuilder is GrowthPlanBuilder
    assert LegacyGrowthStateTransition is GrowthStateTransition
    assert LegacyOpportunityDetector is OpportunityDetector
    assert LegacyOpportunityRanker is OpportunityRanker
    assert LegacyRevenueFeedbackLoop is RevenueFeedbackLoop
    assert LegacyStateSnapshot is StateSnapshot

    memory = LegacyGrowthMemory()
    memory.append({'kind': 'event'})
    assert memory.events == [{'kind': 'event'}]
    assert LegacyGrowthPlanBuilder().build([{'channel': 'ads'}]) == {'count': 1, 'channels': ['ads']}
    assert LegacyGrowthStateTransition().next_state('a', 'b') == 'a->b'
    assert LegacyOpportunityDetector().detect([{'score': 0.1}, {'score': 0.0}]) == [{'score': 0.1}]
    assert LegacyOpportunityRanker().rank([{'score': 0.1}, {'score': 0.9}])[0]['score'] == 0.9
    assert LegacyRevenueFeedbackLoop().apply({'status': 'ok'}, 3.0) == {
        'action_result': {'status': 'ok'},
        'revenue_delta': 3.0,
    }
    assert LegacyStateSnapshot(business_id='x').business_id == 'x'
