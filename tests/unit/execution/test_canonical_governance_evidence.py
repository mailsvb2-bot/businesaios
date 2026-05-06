from __future__ import annotations

from execution.business_memory_governance import BusinessMemoryFitReport
from execution.business_memory_promotion import BusinessMemoryPromotionHelper
from execution.canonical_governance_evidence import canonical_governance_evidence, governance_evidence_roundtrip


def test_canonical_governance_evidence_builds_promotion_snapshot() -> None:
    evidence = canonical_governance_evidence(
        governance_action='promote_baseline',
        baseline_name='baseline-1',
        candidate_record={
            'run_id': 'run-1',
            'tenant_id': 'tenant-1',
            'business_id': 'biz-1',
            'goal': 'grow revenue',
            'final_feedback': {'verification_status': 'verified', 'goal_score': 0.9},
        },
        business_memory_summary={'tenant_id': 'tenant-1', 'business_id': 'biz-1', 'total_runs': 4},
        fit_report={'approved': True, 'score': 0.8, 'reasons': ['goal_matches_active_goal'], 'summary': 'ok'},
        scenario_alignment={'scenario': 'growth', 'aligned': True, 'score': 0.3, 'reasons': ['match']},
    )
    assert evidence['governance_action'] == 'promote_baseline'
    assert evidence['candidate_run_id'] == 'run-1'
    assert evidence['business_memory_fit']['approved'] is True
    assert evidence['scenario_memory_alignment']['aligned'] is True


def test_governance_evidence_roundtrip_reads_nested_governance_payload() -> None:
    payload = {
        'governance_evidence': {
            'governance_action': 'promote_baseline',
            'baseline_name': 'baseline-1',
            'candidate_run_id': 'run-1',
            'business_memory_summary': {
                'tenant_id': 'tenant-1',
                'business_id': 'biz-1',
                'total_runs': 3,
            },
        }
    }
    verified = governance_evidence_roundtrip(
        expected_memory_summary={'tenant_id': 'tenant-1', 'business_id': 'biz-1', 'total_runs': 3},
        governance_payload=payload,
    )
    assert verified['ok'] is True
    assert verified['candidate_run_id'] == 'run-1'


def test_business_memory_promotion_helper_embeds_governance_evidence() -> None:
    helper = BusinessMemoryPromotionHelper()
    evidence = helper.build_promotion_evidence(
        baseline_name='baseline-1',
        candidate_record={'run_id': 'run-1', 'tenant_id': 'tenant-1', 'business_id': 'biz-1'},
        business_memory_summary={'tenant_id': 'tenant-1', 'business_id': 'biz-1', 'total_runs': 4},
        fit_report=BusinessMemoryFitReport(approved=True, score=0.75, reasons=('goal_matches_active_goal',), summary='ok'),
    )
    assert evidence['governance_evidence']['baseline_name'] == 'baseline-1'
    assert evidence['governance_evidence']['business_memory_fit']['score'] == 0.75
