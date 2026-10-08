from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import APIRouter, HTTPException

from adapters.api.fastapi import business_workspace_provider_routes as workspace
from adapters.api.fastapi import router_support
from config.llm_provider_policy import InMemorySalesAIConsentStore
from governance.rbac_contract import RoleId


class _Handlers:
    def __init__(self, providers=()) -> None:
        self.activated = None
        self.sync_called = False
        self.providers = list(providers)

    def list_provider_catalog(self, *, tenant_id: str, business_id: str):
        return {'tenant_id': tenant_id, 'business_id': business_id, 'providers': list(self.providers)}

    def activate_provider(self, *, payload):
        self.activated = dict(payload)
        return {'ok': True, 'tenant_id': payload['tenant_id'], 'business_id': payload['business_id']}

    def probe_provider_live(self, **kwargs):
        return dict(kwargs)

    def trigger_provider_sync(self, *, payload):
        self.sync_called = True
        return dict(payload)

    def list_provider_sync_history(self, **kwargs):
        return dict(kwargs)


def _principal(*, roles=(RoleId.OWNER,), scopes=('provider_control_plane',)):
    return SimpleNamespace(tenant_id='tenant-session', subject='owner-user', actor_id='owner-user', roles=roles, scopes=scopes, metadata={'business_id': 'business-session', 'principal_kind': 'user'})


def _path_route(router: APIRouter, path: str, method: str):
    for route in router.routes:
        if getattr(route, 'path', None) == path and method in getattr(route, 'methods', set()):
            return route.endpoint
    raise AssertionError(f'route not found: {method} {path}')


def _route(router: APIRouter, method: str):
    return _path_route(router, '/business-workspace/providers', method)


def _truth_rows():
    return {
        'contract-provider': SimpleNamespace(status='contract_only', read_only_supported=True, read_capabilities=('read',), required_credentials=()),
        'partial-provider': SimpleNamespace(status='partial', read_only_supported=True, read_capabilities=('read',), required_credentials=()),
        'hubspot': SimpleNamespace(status='partial', read_only_supported=True, read_capabilities=('contact_sync', 'deal_sync'), required_credentials=('access_token',)),
        'email_connector': SimpleNamespace(status='partial', read_only_supported=False, write_supported=True, read_capabilities=(), required_credentials=()),
    }


def _authenticate_as(monkeypatch, principal) -> None:
    monkeypatch.setattr(router_support, 'authorize_request', lambda **_: (object(), principal))


def test_workspace_scope_requires_owner_and_provider_scope(monkeypatch) -> None:
    _authenticate_as(monkeypatch, _principal())
    _, tenant_id, business_id = workspace._workspace_scope(request=object(), auth_bundle=object())
    assert (tenant_id, business_id) == ('tenant-session', 'business-session')
    for principal in (_principal(roles=()), _principal(scopes=())):
        _authenticate_as(monkeypatch, principal)
        with pytest.raises(HTTPException) as exc:
            workspace._workspace_scope(request=object(), auth_bundle=object())
        assert exc.value.status_code == 403


def test_customer_catalog_fails_closed_for_contract_only_read_plan(monkeypatch) -> None:
    handlers = _Handlers(({'provider_key': 'contract-provider'}, {'provider_key': 'partial-provider'}))
    router = APIRouter()
    workspace.register_business_workspace_provider_routes(router=router, auth_bundle=object(), provider_admin_handlers=handlers)
    _authenticate_as(monkeypatch, _principal())
    monkeypatch.setattr(workspace, 'provider_truth_map', _truth_rows)
    result = asyncio.run(_route(router, 'GET')(object()))
    rows = {row['provider_key']: row for row in result['providers']}
    assert rows['contract-provider']['customer_selectable'] is False
    assert rows['partial-provider']['customer_selectable'] is True
    assert result['write_actions_enabled'] is False


def test_workspace_exposes_canonical_capabilities_with_business_connection_state(monkeypatch) -> None:
    handlers = _Handlers(({'provider_key': 'partial-provider', 'connected': True}, {'provider_key': 'hubspot', 'connected': False}))
    router = APIRouter()
    workspace.register_business_workspace_provider_routes(router=router, auth_bundle=object(), provider_admin_handlers=handlers)
    _authenticate_as(monkeypatch, _principal())
    monkeypatch.setattr(workspace, 'provider_truth_map', _truth_rows)
    captured = {}

    def capability_payloads(**kwargs):
        captured.update(kwargs)
        return [{'id': 'interaction.test', 'providers': [{'provider_key': 'partial-provider', 'connected': True}]}]

    monkeypatch.setattr(workspace, 'list_integration_capability_payloads', capability_payloads)
    result = asyncio.run(_route(router, 'GET')(object()))
    assert captured == {'active_provider_keys': ('partial-provider',)}
    assert result['capabilities'][0]['id'] == 'interaction.test'
    assert result['capabilities_source'] == 'application.business_autonomy.integration_capability_catalog'


def test_activation_ignores_browser_workspace_identity_and_ownership(monkeypatch) -> None:
    handlers = _Handlers()
    router = APIRouter()
    workspace.register_business_workspace_provider_routes(router=router, auth_bundle=object(), provider_admin_handlers=handlers)
    _authenticate_as(monkeypatch, _principal())
    monkeypatch.setattr(workspace, 'provider_truth_map', _truth_rows)

    async def fake_json_body(_request):
        return {'action': 'activate', 'tenant_id': 'tenant-victim', 'business_id': 'business-victim', 'ownership_key': 'attacker-owned', 'requested_by': 'attacker', 'provider_key': 'hubspot', 'external_ref': 'portal-123', 'secrets': {'access_token': 'secret-value'}}

    monkeypatch.setattr(workspace, 'json_body', fake_json_body)
    result = asyncio.run(_route(router, 'POST')(object()))
    assert result['ok'] is True
    assert handlers.activated['tenant_id'] == 'tenant-session'
    assert handlers.activated['business_id'] == 'business-session'
    assert handlers.activated['ownership_key'] == 'owner:owner-user:hubspot'
    assert handlers.activated['requested_by'] == 'owner-user'


def test_write_operation_is_rejected_before_provider_runtime(monkeypatch) -> None:
    handlers = _Handlers()
    router = APIRouter()
    workspace.register_business_workspace_provider_routes(router=router, auth_bundle=object(), provider_admin_handlers=handlers)
    _authenticate_as(monkeypatch, _principal())
    monkeypatch.setattr(workspace, 'provider_truth_map', _truth_rows)

    async def fake_json_body(_request):
        return {'action': 'read', 'provider_key': 'hubspot', 'operation': 'message_send', 'mode': 'live', 'payload': {'tenant_id': 'tenant-victim'}}

    monkeypatch.setattr(workspace, 'json_body', fake_json_body)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_route(router, 'POST')(object()))
    assert exc.value.status_code == 403
    assert handlers.sync_called is False


def test_activation_validation_tracks_entire_provider_truth_matrix(monkeypatch) -> None:
    handlers, router = _Handlers(), APIRouter()
    workspace.register_business_workspace_provider_routes(router=router, auth_bundle=object(), provider_admin_handlers=handlers)
    _authenticate_as(monkeypatch, _principal())
    endpoint, truth_rows = _route(router, 'POST'), workspace.provider_truth_map()

    for provider_key, truth in sorted(truth_rows.items()):
        ready = bool(truth.read_only_supported) and str(truth.status) in workspace._READY
        supplied = {name: f'matrix-{provider_key}-{name}' for name in truth.required_credentials}
        cases = ({}, *({key: value for key, value in supplied.items() if key != missing} for missing in truth.required_credentials))
        for secrets in cases:
            handlers.activated = None

            async def fake_json_body(_request, payload={'action': 'activate', 'provider_key': provider_key, 'external_ref': 'matrix-ref', 'secrets': secrets}):
                return payload

            monkeypatch.setattr(workspace, 'json_body', fake_json_body)
            if not ready:
                with pytest.raises(HTTPException) as exc:
                    asyncio.run(endpoint(object()))
                assert exc.value.status_code == 409
            elif truth.required_credentials:
                with pytest.raises(HTTPException) as exc:
                    asyncio.run(endpoint(object()))
                assert (exc.value.status_code, exc.value.detail) == (422, 'provider_required_credentials_missing')
                assert handlers.activated is None
            else:
                assert asyncio.run(endpoint(object()))['ok'] is True

        if ready and truth.required_credentials:
            async def complete_json_body(_request, payload={'action': 'activate', 'provider_key': provider_key, 'external_ref': 'matrix-ref', 'secrets': supplied}):
                return payload

            monkeypatch.setattr(workspace, 'json_body', complete_json_body)
            assert asyncio.run(endpoint(object()))['ok'] is True
            assert handlers.activated['secrets'] == supplied

    ready_key = next(key for key, truth in truth_rows.items() if truth.read_only_supported and str(truth.status) in workspace._READY)

    async def invalid_json_body(_request):
        return {'action': 'activate', 'provider_key': ready_key, 'external_ref': 'matrix-ref', 'secrets': ['not', 'a', 'mapping']}

    monkeypatch.setattr(workspace, 'json_body', invalid_json_body)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint(object()))
    assert (exc.value.status_code, exc.value.detail) == (422, 'provider_secrets_invalid')


def test_write_only_provider_history_is_owner_readable_without_enabling_provider_reads(monkeypatch) -> None:
    handlers, router = _Handlers(), APIRouter()
    workspace.register_business_workspace_provider_routes(router=router, auth_bundle=object(), provider_admin_handlers=handlers)
    _authenticate_as(monkeypatch, _principal())
    monkeypatch.setattr(workspace, 'provider_truth_map', _truth_rows)
    history = asyncio.run(_route(router, 'GET')(object(), provider_key='email_connector', limit=20))
    assert history == {'tenant_id': 'tenant-session', 'business_id': 'business-session', 'provider_key': 'email_connector', 'limit': 20}
    async def fake_json_body(_request):
        return {'action': 'read', 'provider_key': 'email_connector', 'operation': 'message_send', 'mode': 'live'}
    monkeypatch.setattr(workspace, 'json_body', fake_json_body)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_route(router, 'POST')(object()))
    assert exc.value.status_code == 409
    assert handlers.sync_called is False


def test_sales_ai_settings_are_scoped_to_authenticated_owner(monkeypatch) -> None:
    store = InMemorySalesAIConsentStore()
    router = APIRouter()
    workspace.register_business_workspace_provider_routes(
        router=router,
        auth_bundle=object(),
        provider_admin_handlers=_Handlers(),
        sales_ai_consent_store=store,
    )
    _authenticate_as(monkeypatch, _principal())

    async def fake_json_body(_request):
        return {
            'enabled': True,
            'provider': 'yandexgpt',
            'base_url': 'https://llm.api.cloud.yandex.net/foundationModels/v1',
            'data_mode': 'redacted',
            'customer_notice_confirmed': True,
            'tenant_id': 'tenant-victim',
            'business_id': 'business-victim',
        }

    monkeypatch.setattr(workspace, 'json_body', fake_json_body)
    endpoint = _path_route(router, '/business-workspace/sales-ai', 'POST')
    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint(object()))
    assert (exc.value.status_code, exc.value.detail) == (422, 'sales_ai_unknown_settings_fields')
    assert store.get(tenant_id='tenant-session', business_id='business-session') is None


def test_sales_ai_owner_can_enable_read_and_revoke_with_revision(monkeypatch) -> None:
    store = InMemorySalesAIConsentStore()
    router = APIRouter()
    workspace.register_business_workspace_provider_routes(
        router=router,
        auth_bundle=object(),
        provider_admin_handlers=_Handlers(),
        sales_ai_consent_store=store,
    )
    _authenticate_as(monkeypatch, _principal())
    post = _path_route(router, '/business-workspace/sales-ai', 'POST')
    get = _path_route(router, '/business-workspace/sales-ai', 'GET')

    async def enable_body(_request):
        return {
            'enabled': True,
            'provider': 'YandexGPT',
            'base_url': 'https://LLM.API.CLOUD.YANDEX.NET/foundationModels/v1/',
            'data_mode': 'redacted',
            'customer_notice_confirmed': True,
        }

    monkeypatch.setattr(workspace, 'json_body', enable_body)
    enabled = asyncio.run(post(object()))
    assert enabled['enabled'] is True
    assert enabled['provider'] == 'yandexgpt'
    assert enabled['consent_epoch'] == 1
    assert enabled['revision'] == 1
    assert asyncio.run(get(object())) == enabled

    async def revoke_body(_request):
        return {
            'enabled': False,
            'data_mode': 'no_cloud',
            'customer_notice_confirmed': False,
            'expected_revision': 1,
        }

    monkeypatch.setattr(workspace, 'json_body', revoke_body)
    revoked = asyncio.run(post(object()))
    assert revoked['enabled'] is False
    assert revoked['data_mode'] == 'no_cloud'
    assert revoked['consent_epoch'] == 2
    assert revoked['revision'] == 2


def test_sales_ai_enable_requires_notice_and_rejects_stale_revision(monkeypatch) -> None:
    store = InMemorySalesAIConsentStore()
    router = APIRouter()
    workspace.register_business_workspace_provider_routes(
        router=router,
        auth_bundle=object(),
        provider_admin_handlers=_Handlers(),
        sales_ai_consent_store=store,
    )
    _authenticate_as(monkeypatch, _principal())
    post = _path_route(router, '/business-workspace/sales-ai', 'POST')

    async def missing_notice(_request):
        return {
            'enabled': True,
            'provider': 'openai_compat',
            'base_url': 'https://api.openai.com/v1',
            'data_mode': 'redacted',
            'customer_notice_confirmed': False,
        }

    monkeypatch.setattr(workspace, 'json_body', missing_notice)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(post(object()))
    assert exc.value.status_code == 422
    assert 'confirmed customer notice' in str(exc.value.detail)

    async def valid(_request):
        return {
            'enabled': True,
            'provider': 'openai_compat',
            'base_url': 'https://api.openai.com/v1',
            'data_mode': 'redacted',
            'customer_notice_confirmed': True,
        }

    monkeypatch.setattr(workspace, 'json_body', valid)
    assert asyncio.run(post(object()))['revision'] == 1

    async def stale(_request):
        return {
            'enabled': False,
            'data_mode': 'no_cloud',
            'customer_notice_confirmed': False,
            'expected_revision': 99,
        }

    monkeypatch.setattr(workspace, 'json_body', stale)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(post(object()))
    assert (exc.value.status_code, exc.value.detail) == (409, 'sales_ai_settings_concurrent_update')


def test_sales_ai_owner_analysis_is_advisory_only_and_session_scoped(monkeypatch) -> None:
    store = InMemorySalesAIConsentStore()
    store.configure(
        tenant_id='tenant-session',
        business_id='business-session',
        enabled=True,
        provider='openai_compat',
        base_url='https://api.openai.com/v1',
        data_mode='redacted',
        customer_notice_confirmed=True,
        actor='owner-user',
        reason='enable',
    )
    router = APIRouter()
    workspace.register_business_workspace_provider_routes(
        router=router,
        auth_bundle=object(),
        provider_admin_handlers=_Handlers(),
        sales_ai_consent_store=store,
    )
    _authenticate_as(monkeypatch, _principal())
    captured = {}

    def analyze(**kwargs):
        captured.update(kwargs)
        return {
            'ok': True,
            'provider': 'openai_compat',
            'model': 'gpt-test',
            'consent_epoch': 1,
            'data_mode': 'redacted',
            'text_was_redacted': True,
            'observation': {'intent': 'service_interest'},
            'decision_inputs': {'evidence_score': 0.8},
        }

    monkeypatch.setattr(workspace, 'analyze_sales_ai_message', analyze)

    async def analysis_body(_request):
        return {
            'customer_text': 'Хочу узнать подробнее',
            'current_stage': 'engaged',
            'source_kind': 'telegram',
        }

    monkeypatch.setattr(workspace, 'json_body', analysis_body)
    endpoint = _path_route(router, '/business-workspace/sales-ai/analyze', 'POST')
    result = asyncio.run(endpoint(object()))

    assert captured['tenant_id'] == 'tenant-session'
    assert captured['business_id'] == 'business-session'
    assert captured['provider'] == 'openai_compat'
    assert captured['expected_epoch'] == 1
    assert captured['consent_store'] is store
    assert result['tenant_id'] == 'tenant-session'
    assert result['business_id'] == 'business-session'
    assert result['source'] == 'owner_supplied_customer_text'
    assert result['advisory_only'] is True
    assert result['execution_allowed'] is False
    assert result['decision_authority'] == 'DecisionCore'
    assert 'action_kind' not in result.get('decision_inputs', {})


def test_sales_ai_owner_analysis_rejects_scope_spoof_before_model(monkeypatch) -> None:
    store = InMemorySalesAIConsentStore()
    store.configure(
        tenant_id='tenant-session',
        business_id='business-session',
        enabled=True,
        provider='openai_compat',
        base_url='https://api.openai.com/v1',
        data_mode='redacted',
        customer_notice_confirmed=True,
        actor='owner-user',
        reason='enable',
    )
    router = APIRouter()
    workspace.register_business_workspace_provider_routes(
        router=router,
        auth_bundle=object(),
        provider_admin_handlers=_Handlers(),
        sales_ai_consent_store=store,
    )
    _authenticate_as(monkeypatch, _principal())
    called = False

    def analyze(**_kwargs):
        nonlocal called
        called = True
        return {'ok': True}

    monkeypatch.setattr(workspace, 'analyze_sales_ai_message', analyze)

    async def spoofed_body(_request):
        return {
            'customer_text': 'hello',
            'tenant_id': 'tenant-victim',
            'business_id': 'business-victim',
        }

    monkeypatch.setattr(workspace, 'json_body', spoofed_body)
    endpoint = _path_route(router, '/business-workspace/sales-ai/analyze', 'POST')
    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint(object()))
    assert (exc.value.status_code, exc.value.detail) == (
        422,
        'sales_ai_unknown_analysis_fields',
    )
    assert called is False


def test_sales_ai_owner_analysis_requires_consent(monkeypatch) -> None:
    store = InMemorySalesAIConsentStore()
    router = APIRouter()
    workspace.register_business_workspace_provider_routes(
        router=router,
        auth_bundle=object(),
        provider_admin_handlers=_Handlers(),
        sales_ai_consent_store=store,
    )
    _authenticate_as(monkeypatch, _principal())

    async def analysis_body(_request):
        return {'customer_text': 'hello'}

    monkeypatch.setattr(workspace, 'json_body', analysis_body)
    endpoint = _path_route(router, '/business-workspace/sales-ai/analyze', 'POST')
    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint(object()))
    assert (exc.value.status_code, exc.value.detail) == (409, 'sales_ai_consent_missing')


def test_sales_ai_owner_analysis_surfaces_revoked_consent_and_provider_failure(monkeypatch) -> None:
    store = InMemorySalesAIConsentStore()
    store.configure(
        tenant_id='tenant-session',
        business_id='business-session',
        enabled=True,
        provider='openai_compat',
        base_url='https://api.openai.com/v1',
        data_mode='redacted',
        customer_notice_confirmed=True,
        actor='owner-user',
        reason='enable',
    )
    router = APIRouter()
    workspace.register_business_workspace_provider_routes(
        router=router,
        auth_bundle=object(),
        provider_admin_handlers=_Handlers(),
        sales_ai_consent_store=store,
    )
    _authenticate_as(monkeypatch, _principal())

    async def analysis_body(_request):
        return {'customer_text': 'hello'}

    monkeypatch.setattr(workspace, 'json_body', analysis_body)
    endpoint = _path_route(router, '/business-workspace/sales-ai/analyze', 'POST')

    monkeypatch.setattr(
        workspace,
        'analyze_sales_ai_message',
        lambda **_: (_ for _ in ()).throw(PermissionError('sales_ai_consent_disabled')),
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(endpoint(object()))
    assert (exc.value.status_code, exc.value.detail) == (409, 'sales_ai_consent_disabled')

    monkeypatch.setattr(
        workspace,
        'analyze_sales_ai_message',
        lambda **_: {
            'ok': False,
            'error': 'missing_api_key',
            'provider': 'openai_compat',
            'model': 'gpt-test',
        },
    )
    result = asyncio.run(endpoint(object()))
    assert result['ok'] is False
    assert result['error'] == 'missing_api_key'
    assert result['advisory_only'] is True
    assert result['execution_allowed'] is False


def test_sales_ai_unconfigured_disable_enforces_optimistic_revision(monkeypatch) -> None:
    store = InMemorySalesAIConsentStore()
    router = APIRouter()
    workspace.register_business_workspace_provider_routes(
        router=router, auth_bundle=object(), provider_admin_handlers=_Handlers(),
        sales_ai_consent_store=store,
    )
    _authenticate_as(monkeypatch, _principal())
    post = _path_route(router, '/business-workspace/sales-ai', 'POST')

    for expected, expected_status in ((True, 422), ("1", 422), (1, 409)):
        async def invalid(_request, revision=expected):
            return {'enabled': False, 'expected_revision': revision}
        monkeypatch.setattr(workspace, 'json_body', invalid)
        with pytest.raises(HTTPException) as error:
            asyncio.run(post(object()))
        assert error.value.status_code == expected_status
        assert store.get(tenant_id='tenant-session', business_id='business-session') is None

    async def valid(_request):
        return {'enabled': False, 'expected_revision': 0}
    monkeypatch.setattr(workspace, 'json_body', valid)
    result = asyncio.run(post(object()))
    assert result['configured'] is False
    assert result['enabled'] is False
    assert result['revision'] == 0


@pytest.mark.parametrize(
    ("field", "bad_value", "expected_detail"),
    [
        ("customer_text", ["private", "message"], "sales_ai_customer_text_must_be_1_to_12000_chars"),
        ("customer_text", {"text": "private"}, "sales_ai_customer_text_must_be_1_to_12000_chars"),
        ("customer_text", 123, "sales_ai_customer_text_must_be_1_to_12000_chars"),
        ("current_stage", {"stage": "new"}, "sales_ai_analysis_context_invalid"),
        ("source_kind", ["telegram"], "sales_ai_analysis_context_invalid"),
        ("source_kind", 0, "sales_ai_analysis_context_invalid"),
    ],
)
def test_sales_ai_analysis_rejects_nonstring_fields_before_provider_call(
    monkeypatch, field, bad_value, expected_detail
) -> None:
    store = InMemorySalesAIConsentStore()
    store.configure(
        tenant_id='tenant-session', business_id='business-session',
        enabled=True, provider='openai_compat', base_url='https://api.openai.com/v1',
        data_mode='redacted', customer_notice_confirmed=True,
        actor='owner-user', reason='enable',
    )
    router = APIRouter()
    workspace.register_business_workspace_provider_routes(
        router=router, auth_bundle=object(), provider_admin_handlers=_Handlers(),
        sales_ai_consent_store=store,
    )
    _authenticate_as(monkeypatch, _principal())
    payload = {'customer_text': 'hello', 'current_stage': 'new', 'source_kind': 'telegram'}
    payload[field] = bad_value

    async def invalid_body(_request):
        return payload

    def must_not_call_provider(**kwargs):
        pytest.fail('invalid analysis input must not reach Sales AI provider')

    monkeypatch.setattr(workspace, 'json_body', invalid_body)
    monkeypatch.setattr(workspace, 'analyze_sales_ai_message', must_not_call_provider)
    endpoint = _path_route(router, '/business-workspace/sales-ai/analyze', 'POST')
    with pytest.raises(HTTPException) as error:
        asyncio.run(endpoint(object()))
    assert (error.value.status_code, error.value.detail) == (422, expected_detail)


def test_owner_workspace_uses_canonical_channel_catalog_not_a_three_channel_fork(monkeypatch) -> None:
    from contracts.messaging_channels import ALL_CHANNELS

    handlers = _Handlers((
        {'provider_key': 'telegram_bot', 'connected': True},
        {'provider_key': 'vk_messaging', 'connected': False},
    ))
    router = APIRouter()
    workspace.register_business_workspace_provider_routes(
        router=router, auth_bundle=object(), provider_admin_handlers=handlers,
    )
    _authenticate_as(monkeypatch, _principal())
    result = asyncio.run(_route(router, 'GET')(object()))
    channels = {row['channel']: row for row in result['channels']}
    assert tuple(channels) == ALL_CHANNELS
    assert channels['telegram']['connected'] is True
    assert channels['vk']['connected'] is False
    assert channels['max']['connected'] is False
    assert channels['telegram']['capabilities']['buttons'] is True
    assert channels['sms']['capabilities']['attachments'] is False
    assert result['channel_catalog_source'] == 'contracts.messaging_channels.ALL_CHANNELS'
