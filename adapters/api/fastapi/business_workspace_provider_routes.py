from __future__ import annotations

from typing import Any, Mapping

from fastapi import APIRouter, HTTPException, Request, status

from adapters.api.fastapi.router_support import authorize_request, json_body
from application.business_autonomy.provider_truth_matrix import provider_truth_map
from entrypoints.api.provider_admin_route_handlers import ProviderAdminRouteHandlers
from governance.rbac_contract import RoleId

CANON_BUSINESS_WORKSPACE_PROVIDER_ROUTES = True
_READY = frozenset({'live_ready', 'read_only_ready', 'implemented', 'partial'})
_MODES = frozenset({'dry_run', 'live'})


def _workspace_scope(*, request: Request, auth_bundle) -> tuple[object, str, str, str]:
    _, principal = authorize_request(request=request, auth_bundle=auth_bundle)
    if RoleId.OWNER not in tuple(principal.roles) or 'provider_control_plane' not in tuple(principal.scopes):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='owner_provider_scope_required')
    tenant_id = str(principal.tenant_id or '').strip()
    business_id = str(dict(principal.metadata or {}).get('business_id') or '').strip()
    requested_by = str(principal.actor_id or principal.subject or '').strip()
    if not tenant_id or not business_id or not requested_by:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='business_workspace_scope_missing')
    return principal, tenant_id, business_id, requested_by


def _truth(provider_key: str):
    row = provider_truth_map().get(str(provider_key or '').strip())
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='provider_not_found')
    if not bool(row.read_only_supported) or str(row.status) not in _READY:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='provider_not_customer_read_ready')
    return row


def _catalog_for_customer(payload: Mapping[str, Any]) -> dict[str, Any]:
    result, truth = dict(payload), provider_truth_map()
    rows = []
    for raw in list(result.get('providers') or []):
        item, row = dict(raw), truth.get(str(raw.get('provider_key') or '').strip())
        truth_status = 'not_implemented' if row is None else str(row.status)
        selectable = bool(row and row.read_only_supported and truth_status in _READY)
        rows.append({**item, 'truth_status': truth_status, 'customer_selectable': selectable, 'read_supported': selectable, 'write_actions_enabled': False})
    return {**result, 'providers': rows, 'write_actions_enabled': False, 'scope_source': 'authenticated_owner_session'}


def register_business_workspace_provider_routes(*, router: APIRouter, auth_bundle, provider_admin_handlers: ProviderAdminRouteHandlers | None = None) -> None:
    handlers = provider_admin_handlers or ProviderAdminRouteHandlers()

    @router.get('/business-workspace/providers', tags=['business-workspace'])
    async def catalog(request: Request) -> dict[str, Any]:
        _, tenant_id, business_id, _ = _workspace_scope(request=request, auth_bundle=auth_bundle)
        return _catalog_for_customer(handlers.list_provider_catalog(tenant_id=tenant_id, business_id=business_id))

    @router.post('/business-workspace/providers/activate', tags=['business-workspace'])
    async def activate(request: Request) -> dict[str, Any]:
        principal, tenant_id, business_id, requested_by = _workspace_scope(request=request, auth_bundle=auth_bundle)
        provider_key = str((body := await json_body(request)).get('provider_key') or '').strip()
        _truth(provider_key)
        external_ref = str(body.get('external_ref') or '').strip()
        if not external_ref:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='external_ref_required')
        secrets = body.get('secrets') if isinstance(body.get('secrets'), Mapping) else {}
        return handlers.activate_provider(payload={'tenant_id': tenant_id, 'business_id': business_id, 'provider_key': provider_key, 'ownership_key': f'owner:{principal.subject}:{provider_key}', 'requested_by': requested_by, 'external_ref': external_ref, 'region': body.get('region'), 'metadata': dict(body.get('metadata') or {}) if isinstance(body.get('metadata'), Mapping) else {}, 'secrets': {str(k): str(v) for k, v in dict(secrets).items()}})

    @router.post('/business-workspace/providers/{provider_key}/probe', tags=['business-workspace'])
    async def probe(provider_key: str, request: Request) -> dict[str, Any]:
        _, tenant_id, business_id, _ = _workspace_scope(request=request, auth_bundle=auth_bundle)
        _truth(provider_key)
        mode = str((body := await json_body(request)).get('mode') or 'live').strip() or 'live'
        if mode not in _MODES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='unsupported_probe_mode')
        return handlers.probe_provider_live(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, mode=mode)

    @router.post('/business-workspace/providers/{provider_key}/sync', tags=['business-workspace'])
    async def sync(provider_key: str, request: Request) -> dict[str, Any]:
        _, tenant_id, business_id, _ = _workspace_scope(request=request, auth_bundle=auth_bundle)
        truth, body = _truth(provider_key), await json_body(request)
        operation, mode = str(body.get('operation') or '').strip(), str(body.get('mode') or 'live').strip() or 'live'
        if operation not in tuple(truth.read_capabilities):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='provider_write_or_unknown_operation_forbidden')
        if mode not in _MODES:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='unsupported_sync_mode')
        runtime_payload = body.get('payload') if isinstance(body.get('payload'), Mapping) else {}
        return handlers.trigger_provider_sync(payload={'tenant_id': tenant_id, 'business_id': business_id, 'provider_key': provider_key, 'operation': operation, 'mode': mode, 'payload': dict(runtime_payload)})

    @router.get('/business-workspace/providers/{provider_key}/history', tags=['business-workspace'])
    async def history(provider_key: str, request: Request, limit: int = 50) -> dict[str, Any]:
        _, tenant_id, business_id, _ = _workspace_scope(request=request, auth_bundle=auth_bundle)
        _truth(provider_key)
        return handlers.list_provider_sync_history(tenant_id=tenant_id, business_id=business_id, provider_key=provider_key, limit=max(1, min(int(limit), 100)))


__all__ = ['CANON_BUSINESS_WORKSPACE_PROVIDER_ROUTES', 'register_business_workspace_provider_routes']
