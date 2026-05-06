from execution.market_intelligence_approval_gate import MarketIntelligenceApprovalGate
from execution.market_intelligence_circuit_breaker import MarketIntelligenceCircuitBreaker
from execution.market_intelligence_governance import MarketIntelligenceGovernance
from execution.market_intelligence_models import MarketIntelligenceIngestionRequest
from execution.market_intelligence_quota_guard import MarketIntelligenceQuotaGuard
from execution.market_intelligence_risk_policy import MarketIntelligenceRiskPolicy


def test_quota_guard_rejects_over_limit() -> None:
    quota = MarketIntelligenceQuotaGuard(max_requests_per_tenant=5, max_limit_per_request=10)
    request = MarketIntelligenceIngestionRequest(
        tenant_id='tenant-a',
        source_family='marketplace',
        provider='amazon',
        action_type='sync_marketplace_catalog',
        limit=11,
    )
    try:
        quota.consume(request)
    except ValueError as exc:
        assert 'quota guard' in str(exc)
    else:
        raise AssertionError('expected quota guard failure')


def test_risk_policy_flags_ads_spy() -> None:
    risk = MarketIntelligenceRiskPolicy().assess(
        MarketIntelligenceIngestionRequest(
            tenant_id='tenant-a',
            source_family='ads_spy',
            provider='adspy',
            action_type='sync_ads_spy_intelligence',
            limit=10,
        )
    )
    assert risk['requires_approval'] is True


def test_governance_requires_approval_for_high_risk() -> None:
    governance = MarketIntelligenceGovernance(
        approval_gate=MarketIntelligenceApprovalGate(approval_resolver=lambda tenant_id, risk: tenant_id == 'tenant-a')
    )
    request = MarketIntelligenceIngestionRequest(
        tenant_id='tenant-a',
        source_family='ads_library',
        provider='facebook_ad_library',
        action_type='sync_ads_library',
        limit=20,
    )
    _, risk = governance.enforce(request)
    assert risk['requires_approval'] is True


def test_circuit_breaker_opens_after_threshold() -> None:
    breaker = MarketIntelligenceCircuitBreaker(failure_threshold=2)
    breaker.on_failure('amazon')
    breaker.on_failure('amazon')
    try:
        breaker.ensure_open('amazon')
    except ValueError as exc:
        assert 'circuit open' in str(exc)
    else:
        raise AssertionError('expected circuit breaker to open')
