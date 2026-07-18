from __future__ import annotations
from types import SimpleNamespace
from execution.economic_lineage_lock import EconomicLineageLockBuilder
from execution.economic_multi_backend_reconciliation import EconomicMultiBackendReconciliation, EconomicMultiBackendReconciliationBuilder
from execution import economic_multi_backend_reconciliation_support as support

def _rows():
    return {'feedback_rows': [{'event_id': 'feedback-1'}], 'roi_rows': [{'event_id': 'roi-1'}], 'snapshot_rows': [{'snapshot_id': 'snapshot-1'}], 'trace_rows': [{'trace_id': 'trace-1'}], 'metrics_rows': [{'snapshot_id': 'metric-1'}]}

def _scope(tenant='tenant-a', business='business-a', profile='profile-a'):
    return {'tenant_id': tenant, 'business_id': business, 'tenant_tier': 'gold', 'business_tier': 'pro', 'profile_name': profile}

def _manifest(*, scope=None, valid=True, fingerprint='policy-a', corrupt=False):
    scope = dict(scope or _scope())
    scope_lineage = {'parents': []}
    digest = EconomicLineageLockBuilder().build_hash(scope=scope, scope_lineage=scope_lineage)
    return {'scope': scope, 'scope_lineage': scope_lineage, 'lineage_lock': {'lineage_hash': digest if valid else 'invalid-lineage', 'parents': []}, 'manifest_digest': 'corrupt' if corrupt else 'manifest-a', 'generated_at': '2026-07-18T00:00:00Z', 'policy_fingerprint': {'fingerprint': fingerprint}}

def _payload(*, scope=None, valid_lineage=True, fingerprint='policy-a', metadata=None, rows=None, corrupt=False):
    return {'export_manifest': _manifest(scope=scope, valid=valid_lineage, fingerprint=fingerprint, corrupt=corrupt), 'metadata': dict(metadata or {}), **dict(rows or _rows())}

def _node(node_id, *, role='replica', payload=None, leader_epoch=0, store_digest=None, active=True):
    node = {'node_id': node_id, 'backend_role': role, 'leader_epoch': leader_epoch, 'active': active, 'payload': dict(payload or _payload())}
    if store_digest is not None:
        node['store_digest'] = store_digest
    return node

def _build(*, bundle_payloads=(), node_payloads=(), quorum_size=None, policy=None):
    rows = _rows()
    return support.build_reconciliation_fields(**rows, bundle_payloads=bundle_payloads, node_payloads=node_payloads, quorum_size=quorum_size, segment_quorum_policy=policy)

def test_scalar_helpers_and_payload_extraction():
    assert support._safe_dict({'x': 1}) == {'x': 1}
    assert support._safe_dict('x') == {}
    assert support._text(None) == ''
    assert support._text(' x ') == 'x'
    assert support._safe_int('2') == 2
    assert support._safe_int('bad', default=7) == 7
    assert support._extract_ids([{'event_id': ''}, {'event_id': 'a'}, {'memory_key': 'b'}, 'skip'], 'event_id', 'memory_key') == {'a', 'b'}
    metadata_payload = {'metadata': {'scope_profile': _scope()}}
    assert support._scope_signature(metadata_payload)['tenant_id'] == 'tenant-a'
    assert support._scope_signature({}) == {'tenant_id': '', 'business_id': '', 'tenant_tier': '', 'business_tier': '', 'profile_name': ''}
    assert support._history_vector({'metadata': {'replay_epoch': ' 2 ', 'restore_status': 'RESTORING'}}) == {'replay_epoch': '2', 'replay_anchor': '', 'resume_token': '', 'restore_status': 'restoring'}
    assert support._deterministic_node_order({'leader_epoch': 'bad', 'node_name': 'node-a', 'payload': {}})[-1] == 'node-a'
    assert support._segment_sets_from_payload(_rows()) == {'feedback': {'feedback-1'}, 'roi': {'roi-1'}, 'snapshots': {'snapshot-1'}, 'traces': {'trace-1'}, 'metrics': {'metric-1'}}

def test_empty_and_valid_reconciliation_builder_parity():
    empty = support.build_reconciliation_fields(feedback_rows=[], roi_rows=[], snapshot_rows=[], trace_rows=[], metrics_rows=[])
    assert empty['consistent'] is True
    assert empty['quorum_achieved'] is True
    assert empty['authoritative_backend'] is None
    payload = _payload()
    fields = _build(bundle_payloads=[payload], node_payloads=[_node('node-a', payload=payload)])
    assert fields['consistent'] is True
    assert fields['quorum_achieved'] is True
    assert fields['metadata']['lineage_invalid_node_ids'] == []
    result = EconomicMultiBackendReconciliationBuilder().build(**_rows(), bundle_payloads=[payload], node_payloads=[_node('node-a', payload=payload)])
    assert isinstance(result, EconomicMultiBackendReconciliation)
    assert result.to_dict()['consistent'] is True
    assert result.to_dict()['segment_quorum'] == fields['segment_quorum']

def test_invalid_lineage_is_quarantined_and_cannot_be_authoritative():
    bundle = _payload()
    invalid = _payload(valid_lineage=False)
    result = _build(bundle_payloads=[bundle], node_payloads=[_node('bad', role='primary', payload=invalid)])
    assert result['consistent'] is False
    assert result['corrupted_node_ids'] == ('bad',)
    assert result['metadata']['lineage_invalid_node_ids'] == ['bad']
    authority = result['metadata']['backend_authority']
    assert 'bad' in authority['quarantined_backends']
    assert result['authoritative_backend'] is None

def test_strict_segment_policy_is_enforced_above_global_quorum():
    payload = _payload()
    result = _build(bundle_payloads=[payload], node_payloads=[_node('node-a', payload=payload)], quorum_size=1, policy={'feedback': 'strict', 'trace': 'strict'})
    assert result['segment_quorum']['feedback'] == {'support_count': 1, 'support_node_ids': ['node-a'], 'quorum_size': 1, 'effective_required_support': 2, 'achieved': False, 'quorum_achieved': False, 'policy': 'strict', 'required_support': 2}
    assert 'feedback' in result['quorum_failure_segments']
    assert 'traces' in result['quorum_failure_segments']
    assert result['consistent'] is False

def test_duplicate_node_ids_cannot_spoof_quorum():
    payload = _payload()
    duplicate_nodes = [_node('same', payload=payload), _node('same', payload=payload)]
    result = _build(bundle_payloads=[payload], node_payloads=duplicate_nodes, quorum_size=2)
    assert result['metadata']['duplicate_node_ids'] == ['same']
    assert result['segment_quorum']['feedback']['support_count'] == 1
    assert result['segment_quorum']['feedback']['support_node_ids'] == ['same']
    assert 'same' in result['inconsistent_node_ids']
    assert result['quorum_achieved'] is False
    assert result['consistent'] is False

def test_cross_scope_bundles_and_invalid_quorum_fail_closed():
    first = {'bundle_id': 'bundle-a', 'payload': _payload(scope=_scope('tenant-a'))}
    second = {'bundle_id': 'bundle-b', 'payload': _payload(scope=_scope('tenant-b'))}
    result = _build(bundle_payloads=[first, second], quorum_size='not-an-int')
    assert result['metadata']['bundle_scope_mismatch_ids'] == ['bundle-b']
    assert result['metadata']['invalid_quorum_size'] is True
    assert result['consistent'] is False
    same_scope = _build(bundle_payloads=[first, first], quorum_size=0)
    assert same_scope['metadata']['bundle_scope_mismatch_ids'] == []
    boolean = _build(bundle_payloads=[first], quorum_size=True)
    assert boolean['metadata']['invalid_quorum_size'] is True
    assert boolean['consistent'] is False
    zero = _build(bundle_payloads=[first], quorum_size=0)
    assert zero['metadata']['invalid_quorum_size'] is False
    assert zero['quorum_size'] == 1

def test_malformed_node_epochs_are_sanitized_and_fail_closed():
    payload = _payload()
    result = _build(bundle_payloads=[payload], node_payloads=[_node('bad-epoch', payload=payload, leader_epoch='not-an-epoch')])
    assert result['metadata']['invalid_epoch_node_ids'] == ['bad-epoch']
    assert result['consistent'] is False

def test_node_scope_profile_policy_and_content_mismatches_are_reported():
    bundle = _payload()
    wrong_rows = _rows()
    wrong_rows['feedback_rows'] = [{'event_id': 'different'}]
    nodes = [_node('scope', payload=_payload(scope=_scope('tenant-b'))), _node('profile', payload=_payload(scope=_scope(profile='profile-b'))), _node('policy-a', payload=_payload(fingerprint='one')), _node('policy-b', payload=_payload(fingerprint='two')), _node('corrupt', payload=_payload(corrupt=True)), _node('metadata-corrupt', payload=_payload(metadata={'corrupted': True})), _node('import-invalid', payload=_payload(metadata={'import_validation_status': 'invalid'})), _node('content', payload=_payload(rows=wrong_rows))]
    result = _build(bundle_payloads=[bundle], node_payloads=nodes, quorum_size=1)
    assert 'scope' in result['scope_mismatch_node_ids']
    assert {'profile', 'policy-b'}.issubset(result['profile_mismatch_node_ids'])
    assert {'corrupt', 'metadata-corrupt', 'import-invalid'}.issubset(result['corrupted_node_ids'])
    assert 'content' in result['inconsistent_node_ids']
    assert result['consistent'] is False

def test_distributed_extremes_cover_all_fail_closed_issues():
    nodes = [_node('primary-a', role='primary', payload=_payload(metadata={'replay_epoch': '1', 'replay_anchor': 'a'})), _node('primary-b', role='leader', payload=_payload(metadata={'replay_epoch': '2', 'replay_anchor': 'b', 'restore_status': 'restoring'})), _node('stale', payload=_payload(metadata={'restore_status': 'rejoined'}))]
    verdict = support._find_distributed_extremes(node_payloads=nodes, backend_authority=SimpleNamespace(authoritative_backend='primary-a'), split_brain=SimpleNamespace(stale_node_ids=('stale',)), quorum_failure_segments=['feedback'])
    assert set(verdict['issues']) == {'multiple_authoritative_nodes', 'divergent_replay_chains', 'stale_rejoin_detected', 'quorum_partial_restore_conflict'}
    assert verdict['authoritative_backend'] == 'primary-a'
    assert verdict['partial_restore_nodes'] == ['primary-b']
    clear = support._find_distributed_extremes(node_payloads=[], backend_authority=object(), split_brain=object(), quorum_failure_segments=[])
    assert clear['issues'] == []
    assert clear['authoritative_backend'] == ''

def test_split_brain_stale_rejoin_and_quorum_partial_restore_propagate():
    bundle = _payload()
    nodes = [_node('winner', role='primary', payload=_payload(metadata={'replay_epoch': '2', 'replay_anchor': 'new'}), leader_epoch=2, store_digest='winner-digest'), _node('stale', role='replica', payload=_payload(metadata={'replay_epoch': '1', 'replay_anchor': 'old', 'restore_status': 'rejoined'}), leader_epoch=1, store_digest='stale-digest')]
    result = _build(bundle_payloads=[bundle], node_payloads=nodes, quorum_size=2)
    extremes = result['metadata']['distributed_extremes']
    assert result['stale_node_ids'] == ('stale',)
    assert extremes['stale_rejoin_detected'] is True
    assert extremes['divergent_replay_chains'] is True
    assert result['consistent'] is False

def test_dataclass_to_dict_normalizes_tuple_fields():
    value = EconomicMultiBackendReconciliation(bundle_count=1, node_count=2, consistent=False, missing_feedback_event_ids=('f',), missing_roi_event_ids=('r',), missing_snapshot_ids=('s',), missing_trace_ids=('t',), missing_metrics_snapshot_ids=('m',), inconsistent_node_ids=('n',), quorum_size=2, quorum_achieved=False, segment_quorum={'feedback': {'achieved': False}}, scope_mismatch_node_ids=('scope',), profile_mismatch_node_ids=('profile',), corrupted_node_ids=('corrupt',), stale_node_ids=('stale',), authoritative_backend='winner', quorum_failure_segments=('feedback',), metadata={'x': 1})
    payload = value.to_dict()
    assert payload['missing_feedback_event_ids'] == ['f']
    assert payload['stale_node_ids'] == ['stale']
    assert payload['metadata'] == {'x': 1}
