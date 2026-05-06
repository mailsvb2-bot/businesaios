from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from execution.economic_backend_authority import EconomicBackendAuthorityResolver
from execution.economic_split_brain_guard import EconomicSplitBrainGuard
from execution.economic_lineage_lock import EconomicLineageLockBuilder

CANON_ECONOMIC_MULTI_BACKEND_RECONCILIATION = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or '').strip()


def _extract_ids(rows: list[Mapping[str, Any]], *keys: str) -> set[str]:
    result: set[str] = set()
    for row in rows:
        normalized = _safe_dict(row)
        for key in keys:
            value = _text(normalized.get(key))
            if value:
                result.add(value)
                break
    return result


def _scope_signature(payload: Mapping[str, Any]) -> dict[str, str]:
    manifest = _safe_dict(_safe_dict(payload).get('export_manifest'))
    scope = _safe_dict(manifest.get('scope'))
    metadata_scope = _safe_dict(_safe_dict(payload).get('metadata')).get('scope_profile')
    if not scope and isinstance(metadata_scope, Mapping):
        scope = dict(metadata_scope)
    return {
        'tenant_id': _text(scope.get('tenant_id')),
        'business_id': _text(scope.get('business_id')),
        'tenant_tier': _text(scope.get('tenant_tier')),
        'business_tier': _text(scope.get('business_tier')),
        'profile_name': _text(scope.get('profile_name')),
    }



def _history_vector(payload: Mapping[str, Any]) -> dict[str, str]:
    metadata = _safe_dict(_safe_dict(payload).get('metadata'))
    return {
        'replay_epoch': _text(metadata.get('replay_epoch')),
        'replay_anchor': _text(metadata.get('replay_anchor')),
        'resume_token': _text(metadata.get('resume_token')),
        'restore_status': _text(metadata.get('restore_status')).lower(),
    }




def _deterministic_node_order(node: Mapping[str, Any]) -> tuple[object, ...]:
    normalized = _safe_dict(node)
    payload = _safe_dict(normalized.get('payload')) or normalized
    manifest = _safe_dict(payload.get('export_manifest'))
    metadata = _safe_dict(payload.get('metadata'))
    return (
        -int(normalized.get('leader_epoch') or 0),
        _text(metadata.get('replay_epoch')),
        _text(manifest.get('generated_at')),
        _text(manifest.get('manifest_digest')),
        _text(normalized.get('node_id') or normalized.get('node_name')),
    )

def _find_distributed_extremes(
    *,
    node_payloads: list[Mapping[str, Any]],
    backend_authority: object,
    split_brain: object,
    quorum_failure_segments: list[str],
) -> dict[str, Any]:
    authoritative_backend = _text(getattr(backend_authority, 'authoritative_backend', ''))
    stale_nodes = {str(item) for item in getattr(split_brain, 'stale_node_ids', ()) if str(item)}
    authoritative_candidates = []
    replay_epochs: set[str] = set()
    replay_anchors: set[str] = set()
    partial_restore_nodes: list[str] = []
    stale_rejoin_nodes: list[str] = []
    for node in node_payloads:
        normalized = _safe_dict(node)
        node_id = _text(normalized.get('node_id') or normalized.get('node_name'))
        payload = _safe_dict(normalized.get('payload')) or normalized
        history = _history_vector(payload)
        if history['replay_epoch']:
            replay_epochs.add(history['replay_epoch'])
        if history['replay_anchor']:
            replay_anchors.add(history['replay_anchor'])
        if history['restore_status'] in {'started', 'in_progress', 'restoring'}:
            partial_restore_nodes.append(node_id)
        backend_role = _text(normalized.get('backend_role') or _safe_dict(payload.get('metadata')).get('backend_role')).lower()
        if backend_role in {'primary', 'leader', 'authoritative'} and node_id and node_id not in stale_nodes:
            authoritative_candidates.append(node_id)
        if node_id in stale_nodes and history['restore_status'] in {'started', 'in_progress', 'restoring', 'rejoined'}:
            stale_rejoin_nodes.append(node_id)

    issues: list[str] = []
    if len(dict.fromkeys(authoritative_candidates)) > 1:
        issues.append('multiple_authoritative_nodes')
    if len(replay_epochs) > 1 or len(replay_anchors) > 1:
        issues.append('divergent_replay_chains')
    if stale_rejoin_nodes:
        issues.append('stale_rejoin_detected')
    if quorum_failure_segments and partial_restore_nodes:
        issues.append('quorum_partial_restore_conflict')

    return {
        'issues': issues,
        'multiple_authoritative_nodes': len(dict.fromkeys(authoritative_candidates)) > 1,
        'authoritative_candidates': list(dict.fromkeys(authoritative_candidates)),
        'divergent_replay_chains': len(replay_epochs) > 1 or len(replay_anchors) > 1,
        'replay_epochs': sorted(replay_epochs),
        'replay_anchors': sorted(replay_anchors),
        'stale_rejoin_detected': bool(stale_rejoin_nodes),
        'stale_rejoin_nodes': stale_rejoin_nodes,
        'quorum_partial_restore_conflict': bool(quorum_failure_segments and partial_restore_nodes),
        'partial_restore_nodes': partial_restore_nodes,
        'authoritative_backend': authoritative_backend,
    }


def _segment_sets_from_payload(payload: Mapping[str, Any]) -> dict[str, set[str]]:
    normalized = _safe_dict(payload)
    return {
        'feedback': _extract_ids([_safe_dict(row) for row in normalized.get('feedback_rows') or ()], 'event_id', 'memory_key'),
        'roi': _extract_ids([_safe_dict(row) for row in normalized.get('roi_rows') or ()], 'event_id'),
        'snapshots': _extract_ids([_safe_dict(row) for row in normalized.get('snapshot_rows') or ()], 'snapshot_id'),
        'traces': _extract_ids([_safe_dict(row) for row in normalized.get('trace_rows') or ()], 'trace_id'),
        'metrics': _extract_ids([_safe_dict(row) for row in normalized.get('metrics_rows') or ()], 'snapshot_id'),
    }


@dataclass(frozen=True, slots=True)
class EconomicMultiBackendReconciliation:
    bundle_count: int
    node_count: int
    consistent: bool
    missing_feedback_event_ids: tuple[str, ...] = ()
    missing_roi_event_ids: tuple[str, ...] = ()
    missing_snapshot_ids: tuple[str, ...] = ()
    missing_trace_ids: tuple[str, ...] = ()
    missing_metrics_snapshot_ids: tuple[str, ...] = ()
    inconsistent_node_ids: tuple[str, ...] = ()
    quorum_size: int = 1
    quorum_achieved: bool = True
    segment_quorum: dict[str, Any] = field(default_factory=dict)
    scope_mismatch_node_ids: tuple[str, ...] = ()
    profile_mismatch_node_ids: tuple[str, ...] = ()
    corrupted_node_ids: tuple[str, ...] = ()
    stale_node_ids: tuple[str, ...] = ()
    authoritative_backend: str | None = None
    quorum_failure_segments: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'bundle_count': int(self.bundle_count),
            'node_count': int(self.node_count),
            'consistent': bool(self.consistent),
            'missing_feedback_event_ids': list(self.missing_feedback_event_ids),
            'missing_roi_event_ids': list(self.missing_roi_event_ids),
            'missing_snapshot_ids': list(self.missing_snapshot_ids),
            'missing_trace_ids': list(self.missing_trace_ids),
            'missing_metrics_snapshot_ids': list(self.missing_metrics_snapshot_ids),
            'inconsistent_node_ids': list(self.inconsistent_node_ids),
            'quorum_size': int(self.quorum_size),
            'quorum_achieved': bool(self.quorum_achieved),
            'segment_quorum': dict(self.segment_quorum),
            'scope_mismatch_node_ids': list(self.scope_mismatch_node_ids),
            'profile_mismatch_node_ids': list(self.profile_mismatch_node_ids),
            'corrupted_node_ids': list(self.corrupted_node_ids),
            'stale_node_ids': list(self.stale_node_ids),
            'authoritative_backend': self.authoritative_backend,
            'quorum_failure_segments': list(self.quorum_failure_segments),
            'metadata': dict(self.metadata),
        }


class EconomicMultiBackendReconciliationBuilder:
    """
    Read-only integrity checker.

    Important:
    - Does not compute policy.
    - Does not decide.
    - Only reconciles canonical economic stores against exported bundle payloads.
    """

    def build(
        self,
        *,
        feedback_rows: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
        roi_rows: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
        snapshot_rows: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
        trace_rows: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
        metrics_rows: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...],
        bundle_payloads: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] = (),
        node_payloads: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] = (),
        quorum_size: int | None = None,
        segment_quorum_policy: Mapping[str, str] | None = None,
        backend_role_policy: Mapping[str, str] | None = None,
    ) -> EconomicMultiBackendReconciliation:
        local_feedback = [_safe_dict(row) for row in feedback_rows]
        local_roi = [_safe_dict(row) for row in roi_rows]
        local_snapshots = [_safe_dict(row) for row in snapshot_rows]
        local_traces = [_safe_dict(row) for row in trace_rows]
        local_metrics = [_safe_dict(row) for row in metrics_rows]
        bundles = [_safe_dict(bundle) for bundle in bundle_payloads]
        normalized_nodes = sorted([_safe_dict(node) for node in node_payloads], key=_deterministic_node_order)

        bundle_feedback: list[dict[str, Any]] = []
        bundle_roi: list[dict[str, Any]] = []
        bundle_snapshots: list[dict[str, Any]] = []
        bundle_traces: list[dict[str, Any]] = []
        bundle_metrics: list[dict[str, Any]] = []
        reference_scope: dict[str, str] = {}
        for bundle in bundles:
            payload = _safe_dict(bundle.get('payload')) or bundle
            if not reference_scope:
                reference_scope = _scope_signature(payload)
            bundle_feedback.extend(_safe_dict(row) for row in payload.get('feedback_rows') or ())
            bundle_roi.extend(_safe_dict(row) for row in payload.get('roi_rows') or ())
            bundle_snapshots.extend(_safe_dict(row) for row in payload.get('snapshot_rows') or ())
            bundle_traces.extend(_safe_dict(row) for row in payload.get('trace_rows') or ())
            bundle_metrics.extend(_safe_dict(row) for row in payload.get('metrics_rows') or ())

        local_reference = {
            'feedback': _extract_ids(local_feedback, 'event_id', 'memory_key'),
            'roi': _extract_ids(local_roi, 'event_id'),
            'snapshots': _extract_ids(local_snapshots, 'snapshot_id'),
            'traces': _extract_ids(local_traces, 'trace_id'),
            'metrics': _extract_ids(local_metrics, 'snapshot_id'),
        }
        bundle_reference = {
            'feedback': _extract_ids(bundle_feedback, 'event_id', 'memory_key'),
            'roi': _extract_ids(bundle_roi, 'event_id'),
            'snapshots': _extract_ids(bundle_snapshots, 'snapshot_id'),
            'traces': _extract_ids(bundle_traces, 'trace_id'),
            'metrics': _extract_ids(bundle_metrics, 'snapshot_id'),
        }

        missing_feedback = tuple(sorted(local_reference['feedback'] - bundle_reference['feedback']))
        missing_roi = tuple(sorted(local_reference['roi'] - bundle_reference['roi']))
        missing_snapshots = tuple(sorted(local_reference['snapshots'] - bundle_reference['snapshots']))
        missing_traces = tuple(sorted(local_reference['traces'] - bundle_reference['traces']))
        missing_metrics = tuple(sorted(local_reference['metrics'] - bundle_reference['metrics']))

        inconsistent_nodes: list[str] = []
        scope_mismatch_nodes: list[str] = []
        profile_mismatch_nodes: list[str] = []
        corrupted_nodes: list[str] = []
        node_sets: list[tuple[str, dict[str, set[str]]]] = []
        local_scope = reference_scope
        backend_views: list[dict[str, Any]] = []
        reference_policy_fingerprint = ''
        split_brain = EconomicSplitBrainGuard().build(node_views=normalized_nodes)
        stale_node_ids = tuple(sorted(dict.fromkeys(split_brain.stale_node_ids)))
        merge_order = [
            _text(node.get('node_id') or node.get('node_name') or f'node-{index + 1}')
            for index, node in enumerate(normalized_nodes)
        ]
        lineage_invalid_node_ids: list[str] = []

        for index, node in enumerate(normalized_nodes):
            node_id = _text(node.get('node_id') or node.get('node_name') or f'node-{index + 1}')
            payload = _safe_dict(node.get('payload')) or node
            extracted = _segment_sets_from_payload(payload)
            node_sets.append((node_id, extracted))
            manifest = _safe_dict(payload.get('export_manifest'))
            metadata = _safe_dict(payload.get('metadata'))
            lineage_verdict = EconomicLineageLockBuilder().validate(manifest=manifest, expected_scope=local_scope)
            if not lineage_verdict.valid:
                lineage_invalid_node_ids.append(node_id)
            if _text(metadata.get('import_validation_status')) == 'invalid' or _text(manifest.get('manifest_digest')) == 'corrupt' or bool(metadata.get('corrupted')):
                corrupted_nodes.append(node_id)
            node_scope = _scope_signature(payload)
            if local_scope and node_scope and any(node_scope.get(key) and local_scope.get(key) and node_scope.get(key) != local_scope.get(key) for key in ('tenant_id', 'business_id', 'tenant_tier', 'business_tier')):
                scope_mismatch_nodes.append(node_id)
            if local_scope and node_scope and node_scope.get('profile_name') and local_scope.get('profile_name') and node_scope.get('profile_name') != local_scope.get('profile_name'):
                profile_mismatch_nodes.append(node_id)
            policy_fingerprint = _text(_safe_dict(manifest.get('policy_fingerprint')).get('fingerprint'))
            if not reference_policy_fingerprint and policy_fingerprint:
                reference_policy_fingerprint = policy_fingerprint
            elif reference_policy_fingerprint and policy_fingerprint and policy_fingerprint != reference_policy_fingerprint:
                profile_mismatch_nodes.append(node_id)
            if any(extracted[segment_name] != local_reference[segment_name] for segment_name in local_reference):
                inconsistent_nodes.append(node_id)
            backend_views.append(
                {
                    'backend_name': node_id or 'unknown',
                    'backend_role': _text(node.get('backend_role') or metadata.get('backend_role') or 'replica'),
                    'consistency_status': 'corrupted' if node_id in corrupted_nodes else ('stale' if node_id in stale_node_ids else 'healthy'),
                    'snapshot_count': len(extracted.get('snapshots', set())),
                    'trace_count': len(extracted.get('traces', set())),
                    'feedback_count': len(extracted.get('feedback', set())),
                    'roi_count': len(extracted.get('roi', set())),
                    'metrics_count': len(extracted.get('metrics', set())),
                    'scope_mismatch': node_id in scope_mismatch_nodes,
                    'profile_mismatch': node_id in profile_mismatch_nodes,
                    'stale_branch': node_id in stale_node_ids,
                }
            )

        effective_quorum = max(1, int(quorum_size) if quorum_size is not None and int(quorum_size) > 0 else ((len(node_sets) // 2) + 1 if node_sets else 1))
        segment_quorum: dict[str, Any] = {}
        quorum_failure_segments: list[str] = []
        all_segments_quorum = True
        for segment_name, reference_ids in local_reference.items():
            support_node_ids = [node_id for node_id, extracted in node_sets if extracted.get(segment_name, set()) == reference_ids]
            support_count = len(support_node_ids)
            achieved = support_count >= effective_quorum if node_sets else True
            if not achieved:
                all_segments_quorum = False
                quorum_failure_segments.append(segment_name)
            segment_quorum[segment_name] = {
                'support_count': support_count,
                'support_node_ids': support_node_ids,
                'quorum_size': effective_quorum,
                'achieved': achieved,
                'quorum_achieved': achieved,
                'policy': _text(_safe_dict(segment_quorum_policy).get(segment_name) or ''),
                'required_support': {'strict': 2, 'medium': 1, 'soft': 1}.get(_text(_safe_dict(segment_quorum_policy).get(segment_name) or '').lower(), 1),
            }

        backend_authority = EconomicBackendAuthorityResolver().build(
            backend_views=backend_views,
            segment_quorum_policy=segment_quorum_policy,
            backend_role_policy=backend_role_policy,
        )
        distributed_extremes = _find_distributed_extremes(
            node_payloads=normalized_nodes,
            backend_authority=backend_authority,
            split_brain=split_brain,
            quorum_failure_segments=quorum_failure_segments,
        )
        consistent = not any((
            missing_feedback,
            missing_roi,
            missing_snapshots,
            missing_traces,
            missing_metrics,
            tuple(inconsistent_nodes),
            tuple(scope_mismatch_nodes),
            tuple(profile_mismatch_nodes),
            tuple(corrupted_nodes),
            tuple(quorum_failure_segments),
            stale_node_ids,
            tuple(distributed_extremes.get('issues') or ()),
        ))

        return EconomicMultiBackendReconciliation(
            bundle_count=len(bundles),
            node_count=len(normalized_nodes),
            consistent=consistent,
            missing_feedback_event_ids=missing_feedback,
            missing_roi_event_ids=missing_roi,
            missing_snapshot_ids=missing_snapshots,
            missing_trace_ids=missing_traces,
            missing_metrics_snapshot_ids=missing_metrics,
            inconsistent_node_ids=tuple(sorted(dict.fromkeys(inconsistent_nodes))),
            quorum_size=effective_quorum,
            quorum_achieved=all_segments_quorum,
            segment_quorum=segment_quorum,
            scope_mismatch_node_ids=tuple(sorted(dict.fromkeys(scope_mismatch_nodes))),
            profile_mismatch_node_ids=tuple(sorted(dict.fromkeys(profile_mismatch_nodes))),
            corrupted_node_ids=tuple(sorted(dict.fromkeys(corrupted_nodes))),
            stale_node_ids=stale_node_ids,
            authoritative_backend=backend_authority.authoritative_backend,
            quorum_failure_segments=tuple(quorum_failure_segments),
            metadata={
                'owner': 'execution.economic_multi_backend_reconciliation',
                'local_counts': {
                    'feedback': len(local_feedback),
                    'roi': len(local_roi),
                    'snapshots': len(local_snapshots),
                    'traces': len(local_traces),
                    'metrics': len(local_metrics),
                },
                'bundle_counts': {
                    'feedback': len(bundle_feedback),
                    'roi': len(bundle_roi),
                    'snapshots': len(bundle_snapshots),
                    'traces': len(bundle_traces),
                    'metrics': len(bundle_metrics),
                },
                'reference_scope': local_scope,
                'split_brain': split_brain.to_dict(),
                'backend_authority': backend_authority.to_dict(),
                'segment_quorum_policy': dict(_safe_dict(segment_quorum_policy)),
                'backend_role_policy': dict(_safe_dict(backend_role_policy)),
                'deterministic_merge_order': merge_order,
                'lineage_invalid_node_ids': list(dict.fromkeys(lineage_invalid_node_ids)),
                'policy_contract': {
                    'authoritative_backend': backend_authority.authoritative_backend,
                    'authoritative_policy': backend_authority.authoritative_policy,
                    'winner_confirmation_marker': split_brain.winner_confirmation_marker,
                    'authoritative_lineage_digest': split_brain.authoritative_lineage_digest,
                    'stale_lineage_rejections': dict(split_brain.stale_lineage_rejections),
                    'authority_epoch_monotonic': bool(split_brain.epoch_monotonicity_ok),
                    'stale_node_ids': list(stale_node_ids),
                    'quorum_failure_segments': list(quorum_failure_segments),
                },
                'distributed_extremes': distributed_extremes,
            },
        )


__all__ = [
    'CANON_ECONOMIC_MULTI_BACKEND_RECONCILIATION',
    'EconomicMultiBackendReconciliation',
    'EconomicMultiBackendReconciliationBuilder',
]
