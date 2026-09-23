import pytest

from application.business_autonomy.adapters.api_business_adapter import (
    ApiBusinessChannelAdapter,
    LiveApiBusinessChannelAdapter,
)
from application.business_autonomy.channel_contracts import (
    ChannelExecutionEnvelope,
    ChannelIdentity,
    ChannelKind,
)
from application.business_autonomy.contracts import (
    BusinessExecutionEvidence,
    BusinessExecutionRequest,
    BusinessExecutionResult,
    BusinessGoalEnvelope,
    ExecutionVerdict,
    IntegrationMode,
    PolicyConstraint,
)
from application.business_autonomy.policy_semantics_guard import PolicySemanticsGuard
from interfaces.api.business_autonomy_route_handlers import build_business_autonomy_route_handlers
from tests.support.business_autonomy import build_explicitly_onboarded_service


def test_policy_semantics_guard_rejects_conflict() -> None:
    guard = PolicySemanticsGuard()
    with pytest.raises(ValueError):
        guard.normalize(
            {
                'autonomy_tier': 'supervised',
                'autonomy': 'full_autonomy',
            }
        )


@pytest.mark.asyncio
async def test_website_business_uses_supervised_adapter_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    service = build_explicitly_onboarded_service(tenant_id='tenant-demo', business_id='site-biz')
    request = BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id='site-biz',
            goal_id='goal-site-1',
            goal_type='profile_publish',
            goal_payload={'estimated_cost': 1.0, 'outbound_count': 1},
            simulation=True,
            constraints=(
                PolicyConstraint(name='monthly_budget_limit', value=10.0),
                PolicyConstraint(name='outbound_message_limit', value=10),
            ),
            metadata={'tenant_id': 'tenant-demo', 'non_ai_mode': 'supervised', 'autonomy_tier': 'supervised'},
        ),
        integration_mode=IntegrationMode.PLATFORM_DIRECT,
        correlation_id='corr-site-1',
        idempotency_key='idem-site-1',
    )
    result = await service.execute(request)
    assert result.adapter_name == 'website.default'
    assert result.metadata['channel_kind'] == 'website'
    assert result.verdict.value == 'simulated'


def test_business_autonomy_fleet_view_surface(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    handlers = build_business_autonomy_route_handlers()
    view = handlers.get_fleet_view()
    assert view['fleet_cards']
    assert any(row['channel_kind'] in {'api_business', 'website', 'chatbot', 'commerce'} for row in view['business_class_rows'])


def _api_identity() -> ChannelIdentity:
    return ChannelIdentity(
        business_id='biz-api-1',
        tenant_id='tenant-api-1',
        channel_kind=ChannelKind.API_BUSINESS,
        adapter_key='api.live',
        external_ref='external-business-1',
        region='global',
    )


def _api_request(*, simulation: bool = False) -> BusinessExecutionRequest:
    return BusinessExecutionRequest(
        envelope=BusinessGoalEnvelope(
            business_id='biz-api-1',
            goal_id='goal-api-1',
            goal_type='external_business_action',
            simulation=simulation,
            metadata={'tenant_id': 'tenant-api-1'},
        ),
        integration_mode=IntegrationMode.POLICY_GUARDED_DELEGATED,
        correlation_id='corr-api-1',
        idempotency_key='idem-api-1',
    )


def _api_envelope(*, operation: str = 'api_call') -> ChannelExecutionEnvelope:
    return ChannelExecutionEnvelope(
        identity=_api_identity(),
        route_key='external-business',
        operation=operation,
        payload={'action': 'follow_up'},
    )


def test_default_api_business_adapter_does_not_claim_live_writes() -> None:
    adapter = ApiBusinessChannelAdapter()
    descriptors = tuple(adapter.discover_capabilities(identity=ChannelIdentity(
        business_id='biz-api-1',
        tenant_id='tenant-api-1',
        channel_kind=ChannelKind.API_BUSINESS,
        adapter_key='api.default',
        external_ref='external-business-1',
    )))
    invoke = next(item for item in descriptors if item.capability_key == 'api.invoke')
    assert invoke.write_enabled is False
    assert invoke.human_verification_required is True


class _LiveTransport:
    def __init__(self, *, business_id: str = 'biz-api-1', external_effect: bool = True) -> None:
        self.business_id = business_id
        self.external_effect = external_effect
        self.calls = 0

    async def execute(self, *, identity, envelope, request):
        self.calls += 1
        return BusinessExecutionResult(
            verdict=ExecutionVerdict.COMPLETED,
            business_id=self.business_id,
            goal_id=request.envelope.goal_id,
            execution_id=request.correlation_id,
            message='external business action completed',
            evidence=(
                BusinessExecutionEvidence(
                    event_type='external_business_receipt',
                    payload={'receipt_id': 'receipt-1'},
                    timestamp_utc='2026-09-21T20:00:00+00:00',
                    source='external-business',
                ),
            ),
            delegated_to_domain_engine=True,
            metadata={'external_effect': self.external_effect, 'receipt_id': 'receipt-1'},
        )


@pytest.mark.asyncio
async def test_live_api_business_adapter_requires_confirmed_external_evidence() -> None:
    transport = _LiveTransport()
    adapter = LiveApiBusinessChannelAdapter(transport)

    result = await adapter.execute(envelope=_api_envelope(), request=_api_request())

    assert transport.calls == 1
    assert result.verdict is ExecutionVerdict.COMPLETED
    assert result.adapter_name == 'api.live'
    assert result.metadata['transport_configured'] is True
    assert result.metadata['external_effect'] is True


@pytest.mark.asyncio
async def test_live_api_business_adapter_rejects_cross_business_transport_result() -> None:
    adapter = LiveApiBusinessChannelAdapter(_LiveTransport(business_id='other-business'))

    with pytest.raises(RuntimeError, match='API_BUSINESS_TRANSPORT_SCOPE_MISMATCH'):
        await adapter.execute(envelope=_api_envelope(), request=_api_request())


@pytest.mark.asyncio
async def test_live_api_business_adapter_rejects_write_without_external_effect_evidence() -> None:
    adapter = LiveApiBusinessChannelAdapter(_LiveTransport(external_effect=False))

    with pytest.raises(RuntimeError, match='API_BUSINESS_WRITE_EVIDENCE_REQUIRED'):
        await adapter.execute(envelope=_api_envelope(), request=_api_request())
