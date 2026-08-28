from __future__ import annotations

from typing import Any, Mapping

from fastapi import APIRouter, HTTPException, Request, status

from adapters.api.fastapi.router_support import business_owner_scope, json_body
from application.business_autonomy.provider_truth_matrix import provider_truth_map
from entrypoints.api.provider_admin_route_handlers import ProviderAdminRouteHandlers

CANON_BUSINESS_WORKSPACE_PROVIDER_ROUTES = True
_READY = frozenset({'live_ready', 'read_only_ready', 'implemented', 'partial'})


def _workspace_scope(*, request: Request, auth_bundle) -> tuple[object, str, str]:
    principal, tenant_id, business_id = business_owner_scope(request=request, auth_bundle=auth_bundle)
    if 'provider_control_plane' not in tuple(principal.scopes):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='owner_provider_scope_required')
    return principal, tenant_id, business_id


def _truth(provider_key: str):
    if (row := provider_truth_map().get(str(provider_key or '').strip())) is None or not bool(row.read_only_supported) or str(row.status) not in _READY:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='provider_not_customer_read_ready')
    return row


def register_business_workspace_provider_routes(*, router: APIRouter, auth_bundle, provider_admin_handlers: ProviderAdminRouteHandlers | None = None) -> None:
    handlers = provider_admin_handlers or ProviderAdminRouteHandlers()
    @router.get('/business-workspace/providers', tags=['business-workspace'])
    async def provider_workspace(request: Request, provider_key: str | None = None, limit: int = 50) -> dict[str, Any]:
        _, tenant_id, business_id = _workspace_scope(request=request, auth_bundle=auth_bundle)
        if provider_key:
            _truth(provider_key)
            return handlers.list_provider_sync_history(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, limit=max(1, min(int(limit), 100)))
        payload, truth = handlers.list_provider_catalog(tenant_id=tenant_id, business_id=business_id), provider_truth_map()
        rows = [{**dict(raw), 'truth_status': 'not_implemented' if (row := truth.get(str(raw.get('provider_key') or '').strip())) is None else str(row.status), 'customer_selectable': bool(row and row.read_only_supported and str(row.status) in _READY), 'read_supported': bool(row and row.read_only_supported and str(row.status) in _READY), 'write_supported': bool(row and getattr(row, 'write_supported', False)), 'approval_required': bool(row and getattr(row, 'approval_required', False)), 'live_ready': bool(row and getattr(row, 'live_ready', False)), 'write_actions_enabled': False} for raw in list(payload.get('providers') or [])]
        return {**payload, 'providers': rows, 'write_actions_enabled': False, 'scope_source': 'authenticated_owner_session'}
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
        if action == 'read':
            operation, mode = str(body.get('operation') or '').strip(), str(body.get('mode') or 'live').strip() or 'live'
            if mode not in {'dry_run', 'live'} or (operation and operation not in tuple(truth.read_capabilities)):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='provider_read_action_forbidden')
            if not operation:
                return handlers.probe_provider_live(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, mode=mode)
            return handlers.trigger_provider_sync(payload={'tenant_id': tenant_id, 'business_id': business_id, 'provider_key': provider_key, 'operation': operation, 'mode': mode, 'payload': dict(body.get('payload')) if isinstance(body.get('payload'), Mapping) else {}})
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='unsupported_provider_workspace_action')


__all__ = ['CANON_BUSINESS_WORKSPACE_PROVIDER_ROUTES', 'register_business_workspace_provider_routes']
