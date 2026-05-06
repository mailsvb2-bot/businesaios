from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from entrypoints.api.action_models import ExecuteActionRequest
from entrypoints.api.client_outcome_admin_models import ClientOutcomeAdminSummaryRequest
from entrypoints.api.client_outcome_cycle_models import ExecuteClientOutcomeCycleRequest
from entrypoints.api.client_outcome_dispute_models import OpenClientOutcomeDisputeRequest, ReverseClientOutcomeDisputeRequest
from entrypoints.api.client_outcome_models import AmendClientOutcomeOrderRequest, SelectClientOutcomePackageRequest
from entrypoints.api.public_surface_security_guard import PublicSurfaceSecurityGuard
from entrypoints.api.request_context import RequestContext

CANON_FASTAPI_PUBLIC_CORE_AND_ECONOMIC_ROUTE_GROUP = True


def _coerce_body(body: Any):
    model_dump = getattr(body, 'model_dump', None)
    return model_dump() if callable(model_dump) else body


def _to_object(payload: Any) -> Any:
    if hasattr(payload, 'model_dump'):
        return SimpleNamespace(**payload.model_dump())
    if isinstance(payload, dict):
        return SimpleNamespace(**payload)
    return payload


def enforce_public_security(*, route_path: str, request: Request, guard: PublicSurfaceSecurityGuard | Any, body: Any = None) -> RequestContext:
    ctx = RequestContext.from_http_request(request)
    if guard is not None:
        try:
            guard.enforce(route_path=route_path, request_context=ctx, body=_coerce_body(body))
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ctx


def register_public_core_and_economic_routes(
    *,
    router: APIRouter,
    security_guard: PublicSurfaceSecurityGuard | Any,
    handlers: Any,
    headless_handlers: Any | None,
    governance_handlers: Any | None,
    business_memory_handlers: Any | None,
    governance_advanced_handlers: Any | None,
    client_outcome_handlers: Any | None = None,
    economic_handlers: Any | None = None,
) -> None:
    @router.post('/actions/execute')
    def execute_action(payload: ExecuteActionRequest, request: Request):
        ctx = enforce_public_security(route_path='/actions/execute', request=request, guard=security_guard, body=payload)
        return handlers.execute_action(payload, request_context=ctx, idempotency_key=request.headers.get('x-idempotency-key'), action_id=request.headers.get('x-action-id'))

    if headless_handlers is not None:
        @router.post('/headless/execute-goal')
        def execute_goal(payload: Any, request: Request):
            enforce_public_security(route_path='/headless/execute-goal', request=request, guard=security_guard, body=payload)
            return headless_handlers.execute_goal(payload)

    def _memory_route(path: str, method_name: str):
        if business_memory_handlers is None or not hasattr(business_memory_handlers, method_name):
            return
        @router.post(path)
        def _handler(payload: dict[str, Any], request: Request, _method_name=method_name, _path=path):
            enforce_public_security(route_path=_path, request=request, guard=security_guard, body=payload)
            return getattr(business_memory_handlers, _method_name)(_to_object(payload))
    _memory_route('/business-memory/get', 'get_memory')
    _memory_route('/business-memory/summary', 'get_summary')
    _memory_route('/business-memory/recent-runs', 'get_recent_runs')
    _memory_route('/business-memory/failures', 'get_failures')
    _memory_route('/business-memory/wins', 'get_wins')

    if client_outcome_handlers is not None:
        @router.get('/client-outcome/packages')
        def client_outcome_packages(request: Request):
            enforce_public_security(route_path='/client-outcome/packages', request=request, guard=security_guard)
            return client_outcome_handlers.list_packages()

        @router.post('/client-outcome/select')
        def client_outcome_select(payload: SelectClientOutcomePackageRequest, request: Request):
            enforce_public_security(route_path='/client-outcome/select', request=request, guard=security_guard, body=payload)
            return client_outcome_handlers.select_package(now=datetime.now(timezone.utc), request=payload)

        @router.get('/client-outcome/orders/{order_id}')
        def client_outcome_order(order_id: str, request: Request):
            enforce_public_security(route_path='/client-outcome/orders/{order_id}', request=request, guard=security_guard, body={'order_id': order_id})
            return client_outcome_handlers.get_order(order_id=order_id)

        @router.post('/client-outcome/orders/{order_id}/amend')
        def client_outcome_amend(order_id: str, payload: AmendClientOutcomeOrderRequest, request: Request):
            enforce_public_security(route_path='/client-outcome/orders/{order_id}/amend', request=request, guard=security_guard, body=payload)
            try:
                return client_outcome_handlers.amend_order(now=datetime.now(timezone.utc), order_id=order_id, request=payload)
            except ValueError as exc:
                if str(exc) == 'amendment_not_allowed_for_current_commercial_state':
                    raise HTTPException(status_code=409, detail=str(exc)) from exc
                raise

        @router.post('/client-outcome/execute')
        def client_outcome_execute(payload: SelectClientOutcomePackageRequest, request: Request):
            enforce_public_security(route_path='/client-outcome/execute', request=request, guard=security_guard, body=payload)
            return client_outcome_handlers.execute_package(now=datetime.now(timezone.utc), request=payload)

        @router.post('/client-outcome/disputes/open')
        def client_outcome_open_dispute(payload: OpenClientOutcomeDisputeRequest, request: Request):
            enforce_public_security(route_path='/client-outcome/disputes/open', request=request, guard=security_guard, body=payload)
            return client_outcome_handlers.open_dispute(now=datetime.now(timezone.utc), request=payload)

        @router.post('/client-outcome/disputes/reverse')
        def client_outcome_reverse_dispute(payload: ReverseClientOutcomeDisputeRequest, request: Request):
            enforce_public_security(route_path='/client-outcome/disputes/reverse', request=request, guard=security_guard, body=payload)
            return client_outcome_handlers.reverse_dispute(now=datetime.now(timezone.utc), request=payload)

        @router.post('/client-outcome/full-cycle')
        def client_outcome_full_cycle(payload: ExecuteClientOutcomeCycleRequest, request: Request):
            enforce_public_security(route_path='/client-outcome/full-cycle', request=request, guard=security_guard, body=payload)
            return client_outcome_handlers.execute_full_cycle(now=datetime.now(timezone.utc), request=payload)

        @router.get('/client-outcome/lifecycle/{order_id}/{lead_id}')
        def client_outcome_lifecycle(order_id: str, lead_id: str, request: Request):
            enforce_public_security(route_path='/client-outcome/lifecycle/{order_id}/{lead_id}', request=request, guard=security_guard, body={'order_id': order_id, 'lead_id': lead_id})
            return client_outcome_handlers.get_lifecycle(order_id=order_id, lead_id=lead_id)

        @router.get('/client-outcome/commercial-state/{order_id}/{lead_id}')
        def client_outcome_commercial_state(order_id: str, lead_id: str, request: Request):
            enforce_public_security(route_path='/client-outcome/commercial-state/{order_id}/{lead_id}', request=request, guard=security_guard, body={'order_id': order_id, 'lead_id': lead_id})
            return client_outcome_handlers.get_commercial_state(order_id=order_id, lead_id=lead_id)

        @router.get('/client-outcome/corrected-economics/{order_id}/{lead_id}')
        def client_outcome_corrected_economics(order_id: str, lead_id: str, request: Request):
            enforce_public_security(route_path='/client-outcome/corrected-economics/{order_id}/{lead_id}', request=request, guard=security_guard, body={'order_id': order_id, 'lead_id': lead_id})
            return client_outcome_handlers.get_corrected_economics(order_id=order_id, lead_id=lead_id)

        @router.get('/client-outcome/reconciliation/{order_id}/{lead_id}')
        def client_outcome_reconciliation(order_id: str, lead_id: str, request: Request):
            enforce_public_security(route_path='/client-outcome/reconciliation/{order_id}/{lead_id}', request=request, guard=security_guard, body={'order_id': order_id, 'lead_id': lead_id})
            return client_outcome_handlers.get_reconciliation(order_id=order_id, lead_id=lead_id)

        @router.get('/client-outcome/orders/{order_id}/{lead_id}/admin-view')
        def client_outcome_admin_view(order_id: str, lead_id: str, request: Request):
            enforce_public_security(route_path='/client-outcome/orders/{order_id}/{lead_id}/admin-view', request=request, guard=security_guard, body={'order_id': order_id, 'lead_id': lead_id})
            return client_outcome_handlers.get_admin_view(order_id=order_id, lead_id=lead_id)

        @router.post('/client-outcome/admin-summary')
        def client_outcome_admin_summary(payload: ClientOutcomeAdminSummaryRequest, request: Request):
            enforce_public_security(route_path='/client-outcome/admin-summary', request=request, guard=security_guard, body=payload)
            return client_outcome_handlers.build_admin_summary(request=payload)

    if economic_handlers is not None:
        @router.get('/economic/client-outcome-truth/{order_id}/{lead_id}')
        def economic_client_truth(order_id: str, lead_id: str, request: Request):
            enforce_public_security(route_path='/economic/client-outcome-truth/{order_id}/{lead_id}', request=request, guard=security_guard, body={'order_id': order_id, 'lead_id': lead_id})
            return economic_handlers.get_client_outcome_truth(order_id=order_id, lead_id=lead_id)

        @router.get('/economic/business-truth/{order_id}/{lead_id}')
        def economic_business_truth(order_id: str, lead_id: str, request: Request):
            enforce_public_security(route_path='/economic/business-truth/{order_id}/{lead_id}', request=request, guard=security_guard, body={'order_id': order_id, 'lead_id': lead_id})
            return economic_handlers.get_business_truth(order_id=order_id, lead_id=lead_id)

    if governance_handlers is not None:
        for path, name in [
            ('/governance/promote-baseline', 'promote_baseline'),
            ('/governance/select-baseline', 'select_baseline'),
            ('/governance/audit-drift', 'audit_drift'),
            ('/governance/rollback-baseline', 'rollback_baseline'),
        ]:
            if hasattr(governance_handlers, name):
                @router.post(path)
                def _gov(payload: dict[str, Any], request: Request, _name=name, _path=path):
                    enforce_public_security(route_path=_path, request=request, guard=security_guard, body=payload)
                    return getattr(governance_handlers, _name)(_to_object(payload))

    if governance_advanced_handlers is not None:
        for path, name in [
            ('/governance/rollback-recommendation', 'rollback_recommendation'),
            ('/governance/joined-history', 'joined_history'),
            ('/governance/verify-promotion-evidence', 'verify_promotion_evidence'),
            ('/governance/promote-best-for-scenario', 'promote_best_for_scenario'),
            ('/governance/rollback-timeline', 'rollback_timeline'),
            ('/governance/drift-trend', 'drift_trend'),
            ('/governance/business-memory-summary', 'business_memory_summary'),
        ]:
            if hasattr(governance_advanced_handlers, name):
                @router.post(path)
                def _gov_adv(payload: dict[str, Any], request: Request, _name=name, _path=path):
                    enforce_public_security(route_path=_path, request=request, guard=security_guard, body=payload)
                    return getattr(governance_advanced_handlers, _name)(_to_object(payload))


__all__ = [
    'CANON_FASTAPI_PUBLIC_CORE_AND_ECONOMIC_ROUTE_GROUP',
    'enforce_public_security',
    'register_public_core_and_economic_routes',
]
