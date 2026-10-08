from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from adapters.api.fastapi.router_support import business_owner_scope, json_body
from application.business_autonomy.integration_capability_catalog import CAPABILITY_SCHEMA_VERSION, list_integration_capability_payloads
from application.business_autonomy.provider_truth_matrix import provider_truth_map
from contracts.messaging_channels import ALL_CHANNELS
from interfaces.messaging_runtime.capabilities import get_capabilities
from config.llm_provider_policy import (
    PersistentSalesAIConsentStore,
    SalesAIConsentSnapshot,
    SalesAIConsentStore,
    SalesAIDataMode,
)
from entrypoints.api.provider_admin_route_handlers import ProviderAdminRouteHandlers
from runtime.llm_completion_support import analyze_sales_ai_message

CANON_BUSINESS_WORKSPACE_PROVIDER_ROUTES = True
_READY = frozenset({'live_ready', 'read_only_ready', 'implemented', 'partial'})


def _workspace_scope(*, request: Request, auth_bundle) -> tuple[object, str, str]:
    principal, tenant_id, business_id = business_owner_scope(request=request, auth_bundle=auth_bundle)
    if 'provider_control_plane' not in tuple(principal.scopes):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='owner_provider_scope_required')
    return principal, tenant_id, business_id


def _truth(provider_key: str, *, history: bool = False):
    if (row := provider_truth_map().get(str(provider_key or '').strip())) is None or not bool(row.read_only_supported or (history and bool(getattr(row, 'write_supported', False)))) or str(row.status) not in _READY:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='provider_not_customer_read_ready')
    return row


def _sales_ai_settings_payload(
    *,
    tenant_id: str,
    business_id: str,
    snapshot: SalesAIConsentSnapshot | None,
) -> dict[str, Any]:
    if snapshot is None:
        return {
            'tenant_id': tenant_id,
            'business_id': business_id,
            'configured': False,
            'enabled': False,
            'provider': '',
            'base_url': '',
            'data_mode': SalesAIDataMode.REDACTED.value,
            'customer_notice_confirmed': False,
            'consent_epoch': 0,
            'revision': 0,
        }
    return {
        'tenant_id': snapshot.tenant_id,
        'business_id': snapshot.business_id,
        'configured': True,
        'enabled': snapshot.enabled,
        'provider': snapshot.provider,
        'base_url': snapshot.base_url,
        'data_mode': snapshot.data_mode.value,
        'customer_notice_confirmed': snapshot.customer_notice_confirmed,
        'consent_epoch': snapshot.consent_epoch,
        'revision': 0 if snapshot.version is None else snapshot.version.revision,
        'updated_at': snapshot.updated_at.isoformat(),
    }


def register_business_workspace_provider_routes(
    *,
    router: APIRouter,
    auth_bundle,
    provider_admin_handlers: ProviderAdminRouteHandlers | None = None,
    sales_ai_consent_store: SalesAIConsentStore | None = None,
) -> None:
    handlers = provider_admin_handlers or ProviderAdminRouteHandlers()
    consent_store = sales_ai_consent_store or PersistentSalesAIConsentStore()
    @router.get('/business-workspace/providers', tags=['business-workspace'])
    async def provider_workspace(request: Request, provider_key: str | None = None, limit: int = 50) -> dict[str, Any]:
        _, tenant_id, business_id = _workspace_scope(request=request, auth_bundle=auth_bundle)
        if provider_key:
            _truth(provider_key, history=True)
            return handlers.list_provider_sync_history(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, limit=max(1, min(int(limit), 100)))
        payload, truth = handlers.list_provider_catalog(tenant_id=tenant_id, business_id=business_id), provider_truth_map()
        rows = [{**dict(raw), 'truth_status': 'not_implemented' if (row := truth.get(str(raw.get('provider_key') or '').strip())) is None else str(row.status), 'customer_selectable': bool(row and row.read_only_supported and str(row.status) in _READY), 'read_supported': bool(row and row.read_only_supported and str(row.status) in _READY), 'write_supported': bool(row and getattr(row, 'write_supported', False)), 'approval_required': bool(row and getattr(row, 'approval_required', False)), 'live_ready': bool(row and getattr(row, 'live_ready', False)), 'write_actions_enabled': False} for raw in list(payload.get('providers') or [])]
        provider_channels = {
            'telegram': 'telegram_bot', 'vk': 'vk_messaging', 'max': 'max_messaging',
            'whatsapp': 'whatsapp_cloud', 'email': 'email_connector',
            'instagram': 'instagram_messaging', 'messenger': 'messenger_messaging',
            'line': 'line_messaging', 'viber': 'viber_messaging',
            'slack': 'slack_messaging', 'discord': 'discord_messaging',
        }
        provider_by_key = {str(row.get('provider_key') or ''): row for row in rows}
        channel_rows = []
        for channel in ALL_CHANNELS:
            caps = get_capabilities(channel)
            provider_key = provider_channels.get(channel, channel)
            provider_row = provider_by_key.get(provider_key)
            channel_rows.append({
                'channel': channel,
                'provider_key': provider_key if provider_row is not None else None,
                'connectable': bool(provider_row and provider_row.get('customer_selectable')),
                'connected': bool(provider_row and provider_row.get('connected')),
                'capabilities': {
                    key: getattr(caps, key) for key in (
                        'plain_text', 'html', 'buttons', 'attachments',
                        'structured_payload', 'subject_line',
                    )
                },
            })
        return {**payload, 'channels': channel_rows, 'channel_catalog_source': 'contracts.messaging_channels.ALL_CHANNELS', 'providers': rows, 'capabilities': list_integration_capability_payloads(active_provider_keys=tuple(str(raw.get('provider_key') or '').strip() for raw in rows if raw.get('connected'))), 'capabilities_source': 'application.business_autonomy.integration_capability_catalog', 'capabilities_schema_version': CAPABILITY_SCHEMA_VERSION, 'write_actions_enabled': False, 'scope_source': 'authenticated_owner_session'}
    @router.get('/business-workspace/customers', tags=['business-workspace'])
    async def customer_workspace(request: Request, customer_id: str = '') -> dict[str, Any]:
        _, tenant_id, business_id = _workspace_scope(request=request, auth_bundle=auth_bundle)
        try:
            return handlers.get_business_customers(tenant_id=tenant_id, business_id=business_id, customer_id=str(customer_id or '').strip())
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='customer_not_found') from exc
    @router.get('/business-workspace/sales-ai', tags=['business-workspace'])
    async def sales_ai_settings(request: Request) -> dict[str, Any]:
        _, tenant_id, business_id = _workspace_scope(request=request, auth_bundle=auth_bundle)
        return _sales_ai_settings_payload(
            tenant_id=tenant_id,
            business_id=business_id,
            snapshot=consent_store.read_fresh(tenant_id=tenant_id, business_id=business_id),
        )

    @router.post('/business-workspace/sales-ai', tags=['business-workspace'])
    async def update_sales_ai_settings(request: Request) -> dict[str, Any]:
        principal, tenant_id, business_id = _workspace_scope(request=request, auth_bundle=auth_bundle)
        body = await json_body(request)
        allowed = {
            'enabled',
            'provider',
            'base_url',
            'data_mode',
            'customer_notice_confirmed',
            'expected_revision',
        }
        if set(body).difference(allowed):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='sales_ai_unknown_settings_fields',
            )
        enabled = body.get('enabled')
        if not isinstance(enabled, bool):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='sales_ai_enabled_must_be_boolean',
            )
        current = consent_store.read_fresh(tenant_id=tenant_id, business_id=business_id)
        if not enabled and current is None:
            expected = body.get('expected_revision')
            if expected is not None and (isinstance(expected, bool) or not isinstance(expected, int)):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail='sales_ai_expected_revision_must_be_integer',
                )
            if expected not in (None, 0):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail='sales_ai_settings_concurrent_update',
                )
            return _sales_ai_settings_payload(
                tenant_id=tenant_id,
                business_id=business_id,
                snapshot=None,
            )
        provider = str(body.get('provider') or (current.provider if current else '')).strip()
        base_url = str(body.get('base_url') or (current.base_url if current else '')).strip()
        data_mode = str(
            body.get('data_mode')
            or (current.data_mode.value if current else SalesAIDataMode.REDACTED.value)
        ).strip()
        notice = body.get(
            'customer_notice_confirmed',
            current.customer_notice_confirmed if current else False,
        )
        if not isinstance(notice, bool):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='sales_ai_customer_notice_must_be_boolean',
            )
        expected_revision = body.get('expected_revision')
        if expected_revision is not None and (
            isinstance(expected_revision, bool) or not isinstance(expected_revision, int)
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='sales_ai_expected_revision_must_be_integer',
            )
        try:
            stored = consent_store.configure(
                tenant_id=tenant_id,
                business_id=business_id,
                enabled=enabled,
                provider=provider,
                base_url=base_url,
                data_mode=data_mode,
                customer_notice_confirmed=notice,
                actor=str(
                    getattr(principal, 'actor_id', None)
                    or getattr(principal, 'subject', '')
                    or 'owner'
                ),
                reason='owner_sales_ai_settings_update',
                expected_revision=expected_revision,
            )
        except RuntimeError as exc:
            if 'optimistic concurrency' in str(exc):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail='sales_ai_settings_concurrent_update',
                ) from exc
            raise
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
        return _sales_ai_settings_payload(
            tenant_id=tenant_id,
            business_id=business_id,
            snapshot=stored,
        )

    @router.post('/business-workspace/sales-ai/analyze', tags=['business-workspace'])
    async def analyze_sales_ai(request: Request) -> dict[str, Any]:
        _, tenant_id, business_id = _workspace_scope(request=request, auth_bundle=auth_bundle)
        body = await json_body(request)
        allowed = {'customer_text', 'current_stage', 'source_kind'}
        if set(body).difference(allowed):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='sales_ai_unknown_analysis_fields',
            )
        raw_customer_text = body.get('customer_text')
        if not isinstance(raw_customer_text, str):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='sales_ai_customer_text_must_be_1_to_12000_chars',
            )
        customer_text = raw_customer_text.strip()
        if not customer_text or len(customer_text) > 12000:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='sales_ai_customer_text_must_be_1_to_12000_chars',
            )
        raw_stage = body.get('current_stage', 'new')
        raw_source = body.get('source_kind', 'owner_workspace')
        if not isinstance(raw_stage, str) or not isinstance(raw_source, str):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='sales_ai_analysis_context_invalid',
            )
        current_stage = raw_stage.strip()
        source_kind = raw_source.strip()
        if not current_stage or len(current_stage) > 120 or not source_kind or len(source_kind) > 120:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail='sales_ai_analysis_context_invalid',
            )
        snapshot = consent_store.read_fresh(tenant_id=tenant_id, business_id=business_id)
        if snapshot is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='sales_ai_consent_missing',
            )
        try:
            result = await asyncio.to_thread(
                analyze_sales_ai_message,
                tenant_id=tenant_id,
                business_id=business_id,
                provider=snapshot.provider,
                customer_text=customer_text,
                current_stage=current_stage,
                source_kind=source_kind,
                model=None,
                expected_epoch=snapshot.consent_epoch,
                consent_store=consent_store,
            )
        except PermissionError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc
        if not result.get('ok'):
            return {
                **result,
                'tenant_id': tenant_id,
                'business_id': business_id,
                'advisory_only': True,
                'execution_allowed': False,
            }
        return {
            **result,
            'tenant_id': tenant_id,
            'business_id': business_id,
            'source': 'owner_supplied_customer_text',
            'advisory_only': True,
            'execution_allowed': False,
            'decision_authority': 'DecisionCore',
        }

    @router.post('/business-workspace/providers', tags=['business-workspace'])
    async def provider_action(request: Request) -> dict[str, Any]:
        principal, tenant_id, business_id = _workspace_scope(request=request, auth_bundle=auth_bundle)
        body = await json_body(request)
        action, provider_key = str(body.get('action') or '').strip(), str(body.get('provider_key') or '').strip()
        truth = _truth(provider_key)
        if action == 'activate':
            external_ref, secrets = str(body.get('external_ref') or '').strip(), body.get('secrets')
            if not external_ref:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='external_ref_required')
            if secrets is not None and not isinstance(secrets, Mapping):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='provider_secrets_invalid')
            if any(not str((secrets or {}).get(name) or '').strip() for name in tuple(truth.required_credentials)):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='provider_required_credentials_missing')
            return handlers.activate_provider(payload={'tenant_id': tenant_id, 'business_id': business_id, 'provider_key': provider_key, 'ownership_key': f'owner:{principal.subject}:{provider_key}', 'requested_by': str(principal.actor_id or principal.subject), 'external_ref': external_ref, 'region': body.get('region'), 'metadata': dict(body.get('metadata') or {}) if isinstance(body.get('metadata'), Mapping) else {}, 'secrets': {str(k): str(v) for k, v in dict(secrets or {}).items()}})
        if action == 'update_access':
            secrets = body.get('secrets')
            if secrets is not None and not isinstance(secrets, Mapping):
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='provider_secrets_invalid')
            clean = {str(k): str(v).strip() for k, v in dict(secrets or {}).items() if str(v or '').strip()}
            if not clean:
                raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='provider_secrets_required')
            return handlers.rotate_provider(payload={'tenant_id': tenant_id, 'business_id': business_id, 'provider_key': provider_key, 'requested_by': str(principal.actor_id or principal.subject), 'secrets': clean})
        if action == 'read':
            operation, mode = str(body.get('operation') or '').strip(), str(body.get('mode') or 'live').strip() or 'live'
            if mode not in {'dry_run', 'live'} or (operation and operation not in tuple(truth.read_capabilities)):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='provider_read_action_forbidden')
            if not operation:
                return handlers.probe_provider_live(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, mode=mode)
            return handlers.trigger_provider_sync(payload={'tenant_id': tenant_id, 'business_id': business_id, 'provider_key': provider_key, 'operation': operation, 'mode': mode, 'payload': dict(body.get('payload')) if isinstance(body.get('payload'), Mapping) else {}})
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='unsupported_provider_workspace_action')


__all__ = ['CANON_BUSINESS_WORKSPACE_PROVIDER_ROUTES', 'register_business_workspace_provider_routes']
