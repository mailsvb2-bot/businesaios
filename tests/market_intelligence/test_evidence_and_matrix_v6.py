from execution.evidence.market_intelligence import MarketIntelligenceEvidenceVerifier
from execution.market_intelligence_governance import MarketIntelligenceGovernance
from execution.market_intelligence_models import MarketIntelligenceIngestionRequest
from execution.market_intelligence_provider_matrix import MarketIntelligenceProviderMatrix


class _Action:
    action_type = 'sync_marketplace_catalog'


class _ActionResult:
    executed = True
    payload = {'effector': {'verified': True, 'evidence': {'independently_verified': True}}}


def test_provider_matrix_rejects_wrong_provider_for_family() -> None:
    matrix = MarketIntelligenceProviderMatrix()
    try:
        matrix.validate(source_family='marketplace', provider='reddit', action_type='sync_marketplace_catalog')
    except ValueError as exc:
        assert 'not allowed' in str(exc)
    else:
        raise AssertionError('expected provider/family validation error')


def test_governance_rejects_wrong_action_for_family() -> None:
    governance = MarketIntelligenceGovernance()
    req = MarketIntelligenceIngestionRequest(
        tenant_id='t1',
        source_family='marketplace',
        provider='amazon',
        action_type='sync_video_platform',
    )
    try:
        governance.enforce(req)
    except ValueError as exc:
        assert 'does not match source_family' in str(exc)
    else:
        raise AssertionError('expected action/source_family mismatch')


def test_evidence_verifier_is_concrete_and_verifies_payload() -> None:
    verifier = MarketIntelligenceEvidenceVerifier()
    result = verifier.verify(
        request={},
        action=_Action(),
        action_result=_ActionResult(),
        connector_result={
            'connector_payload': {
                'provider': 'amazon',
                'source_family': 'marketplace',
                'operation': 'sync_catalog',
                'records': [{'external_id': 'p1', 'title': 'Product 1'}],
            }
        },
    )
    assert result.verified is True
    assert result.status == 'verified'
    assert 'amazon:marketplace:sync_catalog' in result.external_refs
