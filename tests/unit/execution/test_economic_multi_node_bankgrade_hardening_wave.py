from __future__ import annotations

from execution.economic_backend_authority import EconomicBackendAuthorityResolver
from execution.economic_multi_backend_reconciliation import EconomicMultiBackendReconciliationBuilder
from execution.economic_replay_epoch_guard import EconomicReplayEpochGuard
from execution.economic_split_brain_guard import EconomicSplitBrainGuard


def test_backend_authority_marks_stale_branch_in_role_matrix() -> None:
    verdict = EconomicBackendAuthorityResolver().build(
        backend_views=[
            {'backend_name': 'leader', 'backend_role': 'primary', 'snapshot_count': 3, 'trace_count': 3, 'feedback_count': 3, 'roi_count': 3, 'metrics_count': 1},
            {'backend_name': 'old-primary', 'backend_role': 'primary', 'snapshot_count': 9, 'trace_count': 9, 'feedback_count': 9, 'roi_count': 9, 'metrics_count': 9, 'stale_branch': True},
            {'backend_name': 'advisory-read', 'backend_role': 'advisory', 'snapshot_count': 50},
        ]
    )
    assert verdict.authoritative_backend == 'leader'
    assert 'old-primary' in verdict.stale_backends
    assert verdict.backend_role_matrix['leader'] == 'source_of_truth'
    assert verdict.backend_role_matrix['advisory-read'] == 'advisory_only'
    assert verdict.divergence_matrix['old-primary'] == 'stale_branch'


def test_split_brain_guard_emits_bankgrade_handoff_metadata() -> None:
    verdict = EconomicSplitBrainGuard().build(
        node_views=[
            {'node_id': 'node-a', 'leader_epoch': 5, 'fencing_token': '050', 'active': True, 'store_digest': 'digest-a'},
            {'node_id': 'node-b', 'leader_epoch': 4, 'fencing_token': '040', 'active': True, 'store_digest': 'digest-b'},
        ]
    )
    assert verdict.authoritative_node_id == 'node-a'
    assert verdict.handoff_markers['node-a'].startswith('economic-handoff-winner::node-a')
    assert verdict.handoff_markers['node-b'].startswith('economic-handoff-stale::node-b->node-a')
    assert verdict.stale_branch_digests['node-b'] == 'digest-b'
    assert verdict.metadata['handoff_contract_version'] == 'v4'


def test_reconciliation_uses_policy_contracts_and_marks_stale_node() -> None:
    builder = EconomicMultiBackendReconciliationBuilder()
    result = builder.build(
        feedback_rows=[{'event_id': 'evt-1'}],
        roi_rows=[{'event_id': 'evt-1'}],
        snapshot_rows=[{'snapshot_id': 'snap-1'}],
        trace_rows=[{'trace_id': 'trace-1'}],
        metrics_rows=[{'snapshot_id': 'snap-1'}],
        node_payloads=[
            {
                'node_id': 'node-a',
                'backend_role': 'primary',
                'leader_epoch': 3,
                'fencing_token': '3',
                'store_digest': 'digest-a',
                'feedback_rows': [{'event_id': 'evt-1'}],
                'roi_rows': [{'event_id': 'evt-1'}],
                'snapshot_rows': [{'snapshot_id': 'snap-1'}],
                'trace_rows': [{'trace_id': 'trace-1'}],
                'metrics_rows': [{'snapshot_id': 'snap-1'}],
            },
            {
                'node_id': 'node-b',
                'backend_role': 'primary',
                'leader_epoch': 2,
                'fencing_token': '2',
                'store_digest': 'digest-b',
                'feedback_rows': [{'event_id': 'evt-1'}],
                'roi_rows': [{'event_id': 'evt-1'}],
                'snapshot_rows': [{'snapshot_id': 'snap-1'}],
                'trace_rows': [{'trace_id': 'trace-1'}],
                'metrics_rows': [{'snapshot_id': 'snap-1'}],
            },
        ],
        segment_quorum_policy={'trace': 'strict', 'metrics': 'soft', 'roi': 'medium'},
        backend_role_policy={'primary': 'source_of_truth', 'advisory': 'advisory_only'},
    )
    assert result.authoritative_backend == 'node-a'
    assert result.stale_node_ids == ('node-b',)
    assert result.metadata['backend_authority']['backend_role_matrix']['node-a'] == 'source_of_truth'
    assert result.metadata['segment_quorum_policy']['trace'] == 'strict'


def test_replay_epoch_guard_rejects_partial_progress_conflict() -> None:
    verdict = EconomicReplayEpochGuard().validate(
        current_state={
            'meta': {
                'economic_replay_epoch': 'epoch-1',
                'economic_resume_token': 'resume-a',
                'economic_restore_status': 'in_progress',
            }
        },
        incoming_payload={
            'metadata': {
                'replay_epoch': 'epoch-1',
                'resume_token': 'resume-b',
                'restore_status': 'in_progress',
            }
        },
    )
    assert verdict.accepted is False
    assert verdict.reason == 'economic_replay_partial_progress_conflict'



def test_backend_authority_degrades_when_strict_segment_support_is_missing() -> None:
    verdict = EconomicBackendAuthorityResolver().build(
        backend_views=[
            {'backend_name': 'leader', 'backend_role': 'primary', 'snapshot_count': 1, 'trace_count': 1, 'feedback_count': 3, 'roi_count': 3, 'metrics_count': 1},
            {'backend_name': 'replica', 'backend_role': 'replica', 'snapshot_count': 1, 'trace_count': 1, 'feedback_count': 2, 'roi_count': 2, 'metrics_count': 1},
        ],
        segment_quorum_policy={'trace': 'strict', 'snapshots': 'strict', 'roi': 'medium', 'feedback': 'medium', 'metrics': 'soft'},
    )
    assert verdict.authoritative_backend == 'leader'
    assert verdict.authoritative_policy == 'degraded_authoritative_fallback'
    assert verdict.metadata['authoritative_contract']['winner_denied_segments'] == ['snapshots', 'trace']


def test_replay_epoch_guard_rejects_cross_version_partial_progress_conflict() -> None:
    verdict = EconomicReplayEpochGuard().validate(
        current_state={
            'meta': {
                'economic_replay_epoch': 'epoch-1',
                'economic_resume_token': 'resume-a',
                'economic_restore_status': 'in_progress',
                'economic_bundle_schema_version': '2',
            }
        },
        incoming_payload={
            'metadata': {
                'replay_epoch': 'epoch-1',
                'resume_token': 'resume-a',
                'restore_status': 'in_progress',
                'bundle_schema_version': '3',
            }
        },
    )
    assert verdict.accepted is False
    assert verdict.reason == 'economic_replay_cross_version_conflict'


def test_split_brain_guard_seals_authoritative_lineage_digest() -> None:
    verdict = EconomicSplitBrainGuard().build(
        node_views=[
            {'node_id': 'node-a', 'leader_epoch': 6, 'fencing_token': '060', 'active': True, 'store_digest': 'digest-a', 'parent_lineage_digest': 'lineage-5'},
            {'node_id': 'node-b', 'leader_epoch': 5, 'fencing_token': '050', 'active': True, 'store_digest': 'digest-b', 'parent_lineage_digest': 'lineage-4'},
        ]
    )
    assert verdict.authoritative_lineage_digest
    assert verdict.stale_lineage_rejections['node-b'].startswith('economic-stale-lineage-reject::node-b->node-a')
    assert verdict.metadata['handoff_contract_version'] == 'v4'
    assert verdict.metadata['lineage_sealed'] is True


def test_reconciliation_policy_contract_exposes_lineage_seal() -> None:
    builder = EconomicMultiBackendReconciliationBuilder()
    result = builder.build(
        feedback_rows=[{'event_id': 'evt-1'}],
        roi_rows=[{'event_id': 'evt-1'}],
        snapshot_rows=[{'snapshot_id': 'snap-1'}],
        trace_rows=[{'trace_id': 'trace-1'}],
        metrics_rows=[{'snapshot_id': 'snap-1'}],
        node_payloads=[
            {
                'node_id': 'node-a',
                'backend_role': 'primary',
                'leader_epoch': 4,
                'fencing_token': '4',
                'store_digest': 'digest-a',
                'parent_lineage_digest': 'lineage-3',
                'feedback_rows': [{'event_id': 'evt-1'}],
                'roi_rows': [{'event_id': 'evt-1'}],
                'snapshot_rows': [{'snapshot_id': 'snap-1'}],
                'trace_rows': [{'trace_id': 'trace-1'}],
                'metrics_rows': [{'snapshot_id': 'snap-1'}],
            },
            {
                'node_id': 'node-b',
                'backend_role': 'primary',
                'leader_epoch': 3,
                'fencing_token': '3',
                'store_digest': 'digest-b',
                'parent_lineage_digest': 'lineage-2',
                'feedback_rows': [{'event_id': 'evt-1'}],
                'roi_rows': [{'event_id': 'evt-1'}],
                'snapshot_rows': [{'snapshot_id': 'snap-1'}],
                'trace_rows': [{'trace_id': 'trace-1'}],
                'metrics_rows': [{'snapshot_id': 'snap-1'}],
            },
        ],
    )
    assert result.metadata['policy_contract']['authoritative_lineage_digest']
    assert result.metadata['policy_contract']['authority_epoch_monotonic'] is True



def test_reconciliation_flags_divergent_replay_and_stale_rejoin_extremes() -> None:
    builder = EconomicMultiBackendReconciliationBuilder()
    result = builder.build(
        feedback_rows=[{'event_id': 'evt-1'}],
        roi_rows=[{'event_id': 'evt-1'}],
        snapshot_rows=[{'snapshot_id': 'snap-1'}],
        trace_rows=[{'trace_id': 'trace-1'}],
        metrics_rows=[{'snapshot_id': 'snap-1'}],
        node_payloads=[
            {
                'node_id': 'node-a',
                'backend_role': 'primary',
                'leader_epoch': 5,
                'fencing_token': '5',
                'store_digest': 'digest-a',
                'metadata': {'replay_epoch': 'epoch-a', 'replay_anchor': 'anchor-a', 'restore_status': 'completed'},
                'feedback_rows': [{'event_id': 'evt-1'}],
                'roi_rows': [{'event_id': 'evt-1'}],
                'snapshot_rows': [{'snapshot_id': 'snap-1'}],
                'trace_rows': [{'trace_id': 'trace-1'}],
                'metrics_rows': [{'snapshot_id': 'snap-1'}],
            },
            {
                'node_id': 'node-b',
                'backend_role': 'primary',
                'leader_epoch': 4,
                'fencing_token': '4',
                'store_digest': 'digest-b',
                'metadata': {'replay_epoch': 'epoch-b', 'replay_anchor': 'anchor-b', 'restore_status': 'rejoined'},
                'feedback_rows': [{'event_id': 'evt-1'}],
                'roi_rows': [{'event_id': 'evt-1'}],
                'snapshot_rows': [{'snapshot_id': 'snap-1'}],
                'trace_rows': [{'trace_id': 'trace-1'}],
                'metrics_rows': [{'snapshot_id': 'snap-1'}],
            },
        ],
    )
    extremes = result.metadata['distributed_extremes']
    assert result.consistent is False
    assert extremes['divergent_replay_chains'] is True
    assert extremes['stale_rejoin_detected'] is True
    assert 'divergent_replay_chains' in extremes['issues']
    assert 'stale_rejoin_detected' in extremes['issues']


def test_replay_epoch_guard_rejects_multi_branch_and_anchor_digest_conflict() -> None:
    guard = EconomicReplayEpochGuard()
    multi_branch = guard.validate(
        current_state={'meta': {'economic_replay_epoch': 'epoch-1', 'economic_replay_anchor_digest': 'anchor-digest-a'}},
        incoming_payload={'metadata': {'replay_epoch': 'epoch-1', 'parent_replay_epoch': 'epoch-0', 'replay_chain_depth': 1, 'replay_anchor': 'anchor-1', 'replay_branch_count': 2, 'replay_anchor_digest': 'anchor-digest-a'}},
    )
    assert multi_branch.accepted is False
    assert multi_branch.reason == 'economic_replay_multi_branch_conflict'

    anchor_digest = guard.validate(
        current_state={'meta': {'economic_replay_epoch': 'epoch-1', 'economic_replay_anchor': 'anchor-1', 'economic_replay_anchor_digest': 'anchor-digest-a'}},
        incoming_payload={'metadata': {'replay_epoch': 'epoch-1', 'parent_replay_epoch': 'epoch-0', 'replay_chain_depth': 1, 'replay_history': ['epoch-0'], 'replay_anchor': 'anchor-1', 'replay_anchor_digest': 'anchor-digest-b'}},
    )
    assert anchor_digest.accepted is False
    assert anchor_digest.reason == 'economic_replay_anchor_digest_mismatch'
