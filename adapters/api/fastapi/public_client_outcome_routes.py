from __future__ import annotations

from datetime import datetime, timezone
from fastapi import HTTPException, Request, status
from entrypoints.api.client_outcome_admin_models import ClientOutcomeAdminSummaryRequest
from entrypoints.api.client_outcome_cycle_models import ExecuteClientOutcomeCycleRequest
from entrypoints.api.client_outcome_dispute_models import OpenClientOutcomeDisputeRequest, ReverseClientOutcomeDisputeRequest
from entrypoints.api.client_outcome_models import AmendClientOutcomeOrderRequest, SelectClientOutcomePackageRequest
from entrypoints.api.request_context import RequestContext

def register_public_client_outcome_routes(*, router, client_outcome_handlers, economic_handlers, enforce_public_security, authenticated_tenant, raise_boundary_error) -> None:
    if client_outcome_handlers is not None:
        @router.get('/client-outcome/packages')
        def client_outcome_packages(http_request: Request):
            ctx = RequestContext.from_http_request(http_request, metadata={'route': '/client-outcome/packages'})
            enforce_public_security(route_path='/client-outcome/packages', request_context=ctx, http_request=http_request)
            return client_outcome_handlers.list_packages()

        @router.post('/client-outcome/select')
        def client_outcome_select(http_request: Request, request: SelectClientOutcomePackageRequest):
            ctx = RequestContext.from_http_request(http_request, metadata={'route': '/client-outcome/select'})
            enforce_public_security(route_path='/client-outcome/select', request_context=ctx, body=request.model_dump(), http_request=http_request)
            return client_outcome_handlers.select_package(now=datetime.now(timezone.utc), request=request)

        @router.get('/client-outcome/orders/{order_id}')
        def client_outcome_order(http_request: Request, order_id: str):
            ctx = RequestContext.from_http_request(http_request, metadata={'route': '/client-outcome/orders/{order_id}'})
            ctx = enforce_public_security(route_path='/client-outcome/orders/{order_id}', request_context=ctx, body={'order_id': order_id}, http_request=http_request)
            return client_outcome_handlers.get_order(order_id=order_id, tenant_id=authenticated_tenant(ctx))

        @router.post('/client-outcome/orders/{order_id}/amend')
        def client_outcome_amend(http_request: Request, order_id: str, request: AmendClientOutcomeOrderRequest):
            ctx = RequestContext.from_http_request(http_request, metadata={'route': '/client-outcome/orders/{order_id}/amend'})
            ctx = enforce_public_security(route_path='/client-outcome/orders/{order_id}/amend', request_context=ctx, body=request.model_dump(), http_request=http_request)
            try:
                return client_outcome_handlers.amend_order(now=datetime.now(timezone.utc), order_id=order_id, tenant_id=authenticated_tenant(ctx), request=request)
            except ValueError as exc:
                if str(exc) == 'amendment_not_allowed_for_current_commercial_state':
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
                raise
            except (PermissionError, KeyError) as exc:
                raise_boundary_error(exc)

        @router.post('/client-outcome/execute')
        def client_outcome_execute(http_request: Request, request: SelectClientOutcomePackageRequest):
            ctx = RequestContext.from_http_request(http_request, metadata={'route': '/client-outcome/execute'})
            enforce_public_security(route_path='/client-outcome/execute', request_context=ctx, body=request.model_dump(), http_request=http_request)
            return client_outcome_handlers.execute_package(now=datetime.now(timezone.utc), request=request)

        @router.post('/client-outcome/disputes/open')
        def client_outcome_open_dispute(http_request: Request, request: OpenClientOutcomeDisputeRequest):
            ctx = RequestContext.from_http_request(http_request, metadata={'route': '/client-outcome/disputes/open'})
            ctx = enforce_public_security(route_path='/client-outcome/disputes/open', request_context=ctx, body=request.model_dump(), http_request=http_request)
            try:
                return client_outcome_handlers.open_dispute(now=datetime.now(timezone.utc), request=request, tenant_id=authenticated_tenant(ctx))
            except (PermissionError, KeyError) as exc:
                raise_boundary_error(exc)

        @router.post('/client-outcome/disputes/reverse')
        def client_outcome_reverse_dispute(http_request: Request, request: ReverseClientOutcomeDisputeRequest):
            ctx = RequestContext.from_http_request(http_request, metadata={'route': '/client-outcome/disputes/reverse'})
            ctx = enforce_public_security(route_path='/client-outcome/disputes/reverse', request_context=ctx, body=request.model_dump(), http_request=http_request)
            try:
                return client_outcome_handlers.reverse_dispute(now=datetime.now(timezone.utc), request=request, tenant_id=authenticated_tenant(ctx))
            except (PermissionError, KeyError) as exc:
                raise_boundary_error(exc)

        @router.post('/client-outcome/full-cycle')
        def client_outcome_full_cycle(http_request: Request, request: ExecuteClientOutcomeCycleRequest):
            ctx = RequestContext.from_http_request(http_request, metadata={'route': '/client-outcome/full-cycle'})
            ctx = enforce_public_security(route_path='/client-outcome/full-cycle', request_context=ctx, body=request.model_dump(), http_request=http_request)
            try:
                return client_outcome_handlers.execute_full_cycle(now=datetime.now(timezone.utc), request=request, tenant_id=authenticated_tenant(ctx))
            except (PermissionError, KeyError) as exc:
                raise_boundary_error(exc)

        @router.get('/client-outcome/lifecycle/{order_id}/{lead_id}')
        def client_outcome_lifecycle(http_request: Request, order_id: str, lead_id: str):
            ctx = RequestContext.from_http_request(http_request, metadata={'route': '/client-outcome/lifecycle/{order_id}/{lead_id}'})
            ctx = enforce_public_security(route_path='/client-outcome/lifecycle/{order_id}/{lead_id}', request_context=ctx, body={'order_id': order_id, 'lead_id': lead_id}, http_request=http_request)
            try:
                return client_outcome_handlers.get_lifecycle(order_id=order_id, lead_id=lead_id, tenant_id=authenticated_tenant(ctx))
            except (PermissionError, KeyError) as exc:
                raise_boundary_error(exc)

        @router.get('/client-outcome/commercial-state/{order_id}/{lead_id}')
        def client_outcome_commercial_state(http_request: Request, order_id: str, lead_id: str):
            ctx = RequestContext.from_http_request(http_request, metadata={'route': '/client-outcome/commercial-state/{order_id}/{lead_id}'})
            ctx = enforce_public_security(route_path='/client-outcome/commercial-state/{order_id}/{lead_id}', request_context=ctx, body={'order_id': order_id, 'lead_id': lead_id}, http_request=http_request)
            try:
                return client_outcome_handlers.get_commercial_state(order_id=order_id, lead_id=lead_id, tenant_id=authenticated_tenant(ctx))
            except (PermissionError, KeyError) as exc:
                raise_boundary_error(exc)

        @router.get('/client-outcome/corrected-economics/{order_id}/{lead_id}')
        def client_outcome_corrected_economics(http_request: Request, order_id: str, lead_id: str):
            ctx = RequestContext.from_http_request(http_request, metadata={'route': '/client-outcome/corrected-economics/{order_id}/{lead_id}'})
            ctx = enforce_public_security(route_path='/client-outcome/corrected-economics/{order_id}/{lead_id}', request_context=ctx, body={'order_id': order_id, 'lead_id': lead_id}, http_request=http_request)
            try:
                return client_outcome_handlers.get_corrected_economics(order_id=order_id, lead_id=lead_id, tenant_id=authenticated_tenant(ctx))
            except (PermissionError, KeyError) as exc:
                raise_boundary_error(exc)

        @router.get('/client-outcome/reconciliation/{order_id}/{lead_id}')
        def client_outcome_reconciliation(http_request: Request, order_id: str, lead_id: str):
            ctx = RequestContext.from_http_request(http_request, metadata={'route': '/client-outcome/reconciliation/{order_id}/{lead_id}'})
            ctx = enforce_public_security(route_path='/client-outcome/reconciliation/{order_id}/{lead_id}', request_context=ctx, body={'order_id': order_id, 'lead_id': lead_id}, http_request=http_request)
            try:
                return client_outcome_handlers.get_reconciliation(order_id=order_id, lead_id=lead_id, tenant_id=authenticated_tenant(ctx))
            except (PermissionError, KeyError) as exc:
                raise_boundary_error(exc)

        @router.get('/client-outcome/orders/{order_id}/{lead_id}/admin-view')
        def client_outcome_admin_view(http_request: Request, order_id: str, lead_id: str):
            ctx = RequestContext.from_http_request(http_request, metadata={'route': '/client-outcome/orders/{order_id}/{lead_id}/admin-view'})
            ctx = enforce_public_security(route_path='/client-outcome/orders/{order_id}/{lead_id}/admin-view', request_context=ctx, body={'order_id': order_id, 'lead_id': lead_id}, http_request=http_request)
            try:
                return client_outcome_handlers.get_admin_view(order_id=order_id, lead_id=lead_id, tenant_id=authenticated_tenant(ctx))
            except (PermissionError, KeyError) as exc:
                raise_boundary_error(exc)

        @router.post('/client-outcome/admin-summary')
        def client_outcome_admin_summary(http_request: Request, request: ClientOutcomeAdminSummaryRequest):
            ctx = RequestContext.from_http_request(http_request, metadata={'route': '/client-outcome/admin-summary'})
            ctx = enforce_public_security(route_path='/client-outcome/admin-summary', request_context=ctx, body=request.model_dump(), http_request=http_request)
            try:
                return client_outcome_handlers.build_admin_summary(request=request, tenant_id=authenticated_tenant(ctx))
            except (PermissionError, KeyError) as exc:
                raise_boundary_error(exc)

    if economic_handlers is not None:
        @router.get('/economic/client-outcome-truth/{order_id}/{lead_id}')
        def economic_client_truth(http_request: Request, order_id: str, lead_id: str):
            ctx = RequestContext.from_http_request(http_request, metadata={'route': '/economic/client-outcome-truth/{order_id}/{lead_id}'})
            ctx = enforce_public_security(route_path='/economic/client-outcome-truth/{order_id}/{lead_id}', request_context=ctx, body={'order_id': order_id, 'lead_id': lead_id}, http_request=http_request)
            if client_outcome_handlers is None or not client_outcome_handlers.get_order(order_id=order_id, tenant_id=authenticated_tenant(ctx)).found:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='client_outcome_order_not_found')
            return economic_handlers.get_client_outcome_truth(order_id=order_id, lead_id=lead_id)

        @router.get('/economic/business-truth/{order_id}/{lead_id}')
        def economic_business_truth(http_request: Request, order_id: str, lead_id: str):
            ctx = RequestContext.from_http_request(http_request, metadata={'route': '/economic/business-truth/{order_id}/{lead_id}'})
            ctx = enforce_public_security(route_path='/economic/business-truth/{order_id}/{lead_id}', request_context=ctx, body={'order_id': order_id, 'lead_id': lead_id}, http_request=http_request)
            if client_outcome_handlers is None or not client_outcome_handlers.get_order(order_id=order_id, tenant_id=authenticated_tenant(ctx)).found:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='client_outcome_order_not_found')
            return economic_handlers.get_business_truth(order_id=order_id, lead_id=lead_id)
