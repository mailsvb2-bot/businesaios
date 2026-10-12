"""Verified owner commercial API; uses the canonical order/invoice/offer owners."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request

from adapters.api.fastapi.router_support import business_owner_scope, json_body

CANON_PHASE18_COMMERCIAL_OWNER_API = True


def register_business_workspace_commercial_routes(*, router: APIRouter, auth_bundle, purchases, checkout=None):
    def scope(request):
        _, tenant, business = business_owner_scope(request=request, auth_bundle=auth_bundle)
        return tenant, business

    @router.get("/business-workspace/commercial/offers/{program_id}", tags=["business-workspace"])
    async def offers(program_id: str, request: Request):
        tenant, business = scope(request)
        try:
            program = purchases.programs.get(tenant_id=tenant, business_id=business, program_id=program_id)
            if program["status"] != "active":
                raise ValueError("commercial_program_not_published")
            from core.offers.offer_catalog_resolver import OfferCatalogKey
            catalog = purchases.offers.resolve(key=OfferCatalogKey(
                tenant_id=tenant, business_id=business, product_id=program_id,
            ))
            result = []
            for item in catalog.list_offers():
                try:
                    proof = purchases.priced_offer(
                        tenant_id=tenant, business_id=business, program_id=program_id, offer_id=item.offer_id,
                    )
                except ValueError:
                    continue
                result.append(asdict(proof))
            return {"program_id": program_id, "offers": result}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="commercial_program_or_offer_not_found") from exc

    @router.post("/business-workspace/commercial/orders", tags=["business-workspace"])
    async def create_order(request: Request):
        tenant, business = scope(request)
        body = await json_body(request)
        if set(body) != {"lead_id", "customer_id", "program_id", "offer_id", "idempotency_key"} or (
            not all(isinstance(x, str) for x in body.values())
        ):
            raise HTTPException(status_code=422, detail="commercial_order_fields_invalid")
        try:
            return asdict(purchases.prepare_purchase(tenant_id=tenant, business_id=business, **body))
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="commercial_order_party_not_found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get("/business-workspace/commercial/orders", tags=["business-workspace"])
    async def list_orders(request: Request):
        tenant, business = scope(request)
        result = []
        for order in purchases.orders.list_for_business(tenant_id=tenant, business_id=business):
            if order.order_kind == "commercial_program":
                result.append(_order_status(purchases, tenant, business, order.order_id))
        return {"orders": result}

    @router.get("/business-workspace/commercial/orders/{order_id}", tags=["business-workspace"])
    async def get_order(order_id: str, request: Request):
        tenant, business = scope(request)
        try:
            return _order_status(purchases, tenant, business, order_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="commercial_order_not_found") from exc

    @router.post("/business-workspace/commercial/orders/{order_id}/checkout", tags=["business-workspace"])
    async def open_checkout(order_id: str, request: Request):
        tenant, business = scope(request)
        if checkout is None:
            raise HTTPException(status_code=503, detail="commercial_psp_unconfigured")
        try:
            return asdict(checkout.open_checkout(tenant_id=tenant, business_id=business, order_id=order_id))
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="commercial_order_not_found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


def _order_status(purchases, tenant, business, order_id):
    order, link = purchases._read(tenant_id=tenant, business_id=business, order_id=order_id)
    invoice = purchases.invoices.get(tenant_id=tenant, business_id=business, invoice_id=link["invoice_id"])
    if (invoice.tenant_id != tenant or invoice.business_id != business
            or invoice.total_minor != link["amount_minor"]
            or invoice.currency != link["currency"]
            or dict(invoice.metadata).get("order_id") != order_id):
        raise RuntimeError("commercial_invoice_provenance_invalid")
    return {
        "order_id": order_id, "status": order.lifecycle_status.value,
        "invoice_id": invoice.invoice_id, "invoice_status": invoice.status.value,
        "amount_minor": invoice.total_minor, "paid_minor": invoice.paid_minor,
        "currency": invoice.currency, "offer_id": link["offer_id"],
        "lead_id": link["lead_id"], "customer_id": link["customer_id"],
        "program_id": link["program_id"],
        "provider_verified": False,
    }


__all__ = ["register_business_workspace_commercial_routes", "CANON_PHASE18_COMMERCIAL_OWNER_API"]
