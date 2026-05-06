from execution.canonical_scenario_governance import (
    canonical_scenario_catalog_entry,
    canonical_scenario_namespace,
    canonical_scenario_selection_outcome,
)


def test_canonical_scenario_namespace_builds_stable_baseline_name() -> None:
    payload = canonical_scenario_namespace(scenario='Lead Gen', prefix='scenario', suffix='golden')
    assert payload['scenario_governance']['baseline_name'] == 'scenario:lead_gen:golden'


def test_canonical_scenario_catalog_entry_embeds_scenario_governance() -> None:
    payload = canonical_scenario_catalog_entry(
        scenario='Lead Gen',
        baseline_name='scenario:lead_gen:golden',
        source_run_id='run-1',
        metadata={'label': 'auto'},
    )
    assert payload['scenario_governance']['source_run_id'] == 'run-1'
    assert payload['scenario_governance']['metadata']['label'] == 'auto'


def test_canonical_scenario_selection_outcome_merges_decision_and_catalog() -> None:
    outcome = canonical_scenario_selection_outcome(
        scenario='Lead Gen',
        baseline_name='scenario:lead_gen:golden',
        selected_record={'run_id': 'run-1', 'goal': 'grow', 'tenant_id': 'tenant', 'business_id': 'biz'},
        governance_decision={'governance_decision': {'approved': True, 'confidence': 0.9, 'reasons': ['top_score'], 'summary': 'selected'}},
        catalog_entry={'scenario_governance': {'source_run_id': 'run-1'}},
        metadata={'label': 'auto'},
    )
    assert outcome['scenario_governance']['selected_run_id'] == 'run-1'
    assert outcome['scenario_governance']['approved'] is True
    assert outcome['scenario_governance']['metadata']['label'] == 'auto'
