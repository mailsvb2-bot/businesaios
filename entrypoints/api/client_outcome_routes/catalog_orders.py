from __future__ import annotations

from datetime import datetime

from entrypoints.api.client_outcome_models import (
    AmendClientOutcomeOrderRequest,
    ClientOutcomeExecuteResponse,
    ClientOutcomeOrderAmendResponse,
    ClientOutcomeOrderLookupResponse,
    ClientOutcomeOrderResponse,
    ClientOutcomePackageResponse,
    SelectClientOutcomePackageRequest,
)
from entrypoints.api.client_outcome_routes.module_helpers import _present_order, _require_order_tenant
from lead_outcomes.client_outcome_selection_service import ClientOutcomeSelectionInput


def list_packages(handlers) -> tuple[ClientOutcomePackageResponse, ...]:
    return tuple(
        ClientOutcomePackageResponse(
            package_id=package.package_id,
            label=package.label,
            requested_clients=package.requested_clients,
            price_per_verified_client=package.price_per_verified_client,
            currency=package.currency,
            attribution_window_days=package.attribution_window_days,
            trust_tier=package.trust_tier,
        )
        for package in handlers.package_catalog.list_packages()
    )


def select_package(handlers, *, now: datetime, request: SelectClientOutcomePackageRequest) -> ClientOutcomeOrderResponse:
    selection = handlers.selection_service.select(
        now=now,
        request=ClientOutcomeSelectionInput(
            tenant_id=request.tenant_id,
            business_id=request.business_id,
            package_id=request.package_id,
            requested_clients=request.requested_clients,
            metadata=request.metadata,
        ),
    )
    return _present_order(selection.order)


def get_order(handlers, *, order_id: str, tenant_id: str | None = None) -> ClientOutcomeOrderLookupResponse:
    order = handlers.selection_service.get_order(order_id)
    if order is None or (tenant_id is not None and str(order.tenant_id) != str(tenant_id)):
        return ClientOutcomeOrderLookupResponse(found=False, order=None)
    return ClientOutcomeOrderLookupResponse(found=True, order=_present_order(order))


def amend_order(handlers, *, now: datetime, order_id: str, tenant_id: str, request: AmendClientOutcomeOrderRequest) -> ClientOutcomeOrderAmendResponse:
    current_order = _require_order_tenant(handlers, order_id=order_id, tenant_id=tenant_id)
    selection = handlers.selection_service.amend(
        now=now,
        order_id=order_id,
        request=ClientOutcomeSelectionInput(
            tenant_id=current_order.tenant_id,
            business_id=current_order.business_id,
            package_id=request.package_id,
            requested_clients=request.requested_clients,
            metadata=request.metadata,
        ),
    )
    if selection is None:
        raise KeyError(order_id)
    order = selection.order
    amendments = tuple(dict(item) for item in (order.metadata.get('amendments') or ()))
    return ClientOutcomeOrderAmendResponse(
        order=_present_order(order),
        amendment_count=int(order.metadata.get('amendment_count') or 0),
        amendments=amendments,
    )


def execute_package(handlers, *, now: datetime, request: SelectClientOutcomePackageRequest) -> ClientOutcomeExecuteResponse:
    selection = handlers.selection_service.select(
        now=now,
        request=ClientOutcomeSelectionInput(
            tenant_id=request.tenant_id,
            business_id=request.business_id,
            package_id=request.package_id,
            requested_clients=request.requested_clients,
            metadata=request.metadata,
        ),
    )
    order = selection.order
    enriched_meta = handlers.request_enricher.enrich_metadata(existing_metadata=request.metadata, order=order)
    execution_payload = {
        'mode': 'prepared_contract',
        'goal': f'Acquire {order.package.requested_clients} verified new clients for business {order.business_id} within {order.package.attribution_window_days} days',
        'business_id': order.business_id,
        'tenant_id': order.tenant_id,
        'completed': False,
        'stop_reason': 'prepared_for_headless_execution',
        'steps': [],
        'final_feedback': dict(enriched_meta),
        'capability_view': {},
    }
    return ClientOutcomeExecuteResponse(order=_present_order(order), execution=execution_payload)
