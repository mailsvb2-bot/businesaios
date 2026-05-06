from execution.action_catalog import get_action_spec
from execution.effectors.catalog import build_effector
from execution.evidence.router import build_evidence_router
from execution.effectors.result import EffectorResult
from interfaces.common.connector_registry_matrix import build_connector_registry_matrix_payload


class _Action:
    action_type = 'sync_marketplace_catalog'


def test_action_catalog_exposes_market_intelligence_specs():
    spec = get_action_spec('sync_marketplace_catalog')
    assert spec.action_class == 'market_intelligence_read'
    assert spec.idempotent is True
    assert spec.externally_verified is True


def test_effector_catalog_routes_market_intelligence_actions():
    effector = build_effector('sync_marketplace_catalog')
    result = effector.execute(
        {
            'action_id': 'a-1',
            'payload': {
                'provider': 'amazon',
                'tenant_id': 'tenant-1',
                'query': 'hypnosis',
                'limit': 3,
                'dry_run': True,
            }
        }
    )
    assert isinstance(result, EffectorResult)
    assert result.executed is True
    assert result.verified is False
    connector_payload = result.payload['connector_payload']
    assert connector_payload['provider'] == 'amazon'
    assert connector_payload['source_family'] == 'marketplace'


def test_evidence_router_verifies_market_intelligence_payloads():
    router = build_evidence_router()
    effector = build_effector('sync_marketplace_catalog')
    effector_result = effector.execute(
        {
            'action_id': 'a-2',
            'payload': {
                'provider': 'amazon',
                'tenant_id': 'tenant-1',
                'query': 'coaching',
                'limit': 2,
                'dry_run': True,
            }
        }
    )
    evidence = router.verify(
        request={'tenant_id': 'tenant-1'},
        action=_Action(),
        action_result=effector_result,
        connector_result=effector_result.evidence['connector_payload'],
    )
    assert evidence.status == 'verified'
    assert evidence.payload['connector_result']['verify']['ok'] is True


def test_registry_matrix_includes_market_intelligence_connectors():
    rows = build_connector_registry_matrix_payload()
    market_rows = [row for row in rows if row['domain'] == 'market_intelligence']
    assert market_rows
    assert any(row['connector_name'] == 'amazon' for row in market_rows)
    assert any(row['connector_name'] == 'facebook_ad_library' for row in market_rows)
