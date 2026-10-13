"""Verified owner commercial API; uses the canonical order/invoice/offer owners."""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request

from adapters.api.fastapi.router_support import business_owner_scope, json_body

CANON_PHASE18_COMMERCIAL_OWNER_API = True


def register_business_workspace_commercial_routes(*, router: APIRouter, auth_bundle, purchases, checkout=None, context_reader=None, settlement=None, partner_registry=None):
    def scope(request):
        _, tenant, business = business_owner_scope(request=request, auth_bundle=auth_bundle)
        return tenant, business

    @router.get("/business-workspace/commercial/leads", tags=["business-workspace"])
    async def list_commercial_leads(request: Request):
        tenant, business = scope(request)
        leads = purchases.leads.list_for_business(tenant_id=tenant, business_id=business)
        return {"leads": [
            {
                "lead_id": lead.lead_id,
                "customer_id": lead.customer_id,
                "conversation_id": lead.conversation_id,
                "channel": lead.channel,
                "source": lead.source,
                "sales_stage": lead.status,
                "lifecycle_status": lead.lifecycle_status.value,
                "updated_at_ms": lead.updated_at_ms,
            }
            for lead in leads
            if lead.customer_id and lead.conversation_id and lead.channel
        ]}

    @router.post("/business-workspace/commercial/partner-opportunities/prepare", tags=["business-workspace"])
    async def prepare_partner_campaign_proposal(request: Request):
        """Generate an owner-reviewable proposal, never dispatch partner outreach."""
        from application.partner.growth_advisory import (
            PartnerOpportunity,
            prepare_partner_proposal,
        )

        tenant, business = scope(request)
        if partner_registry is None:
            raise HTTPException(status_code=503, detail="canonical_partner_owner_unavailable")
        body = await json_body(request)
        if set(body) != {
            "candidate", "business_name", "offering", "campaign_topic", "target_url",
        }:
            raise HTTPException(status_code=422, detail="partner_proposal_fields_invalid")
        row = body["candidate"]
        allowed = {
            "partner_id", "name", "topics", "audience_summary", "recent_topic",
            "followers", "contact_basis", "contact_value", "source_url", "competitor",
        }
        if not isinstance(row, dict) or not set(row) <= allowed:
            raise HTTPException(status_code=422, detail="partner_candidate_fields_invalid")
        try:
            candidate = PartnerOpportunity(
                business_id=business,
                **{**row, "topics": tuple(row.get("topics") or ())},
            )
            partner = partner_registry.get(
                tenant_id=tenant, business_id=business,
                partner_id=candidate.partner_id,
            )
            draft = prepare_partner_proposal(
                partner=partner, candidate=candidate,
                business_name=body["business_name"], offering=body["offering"],
                campaign_topic=body["campaign_topic"], target_url=body["target_url"],
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="partner_proposal_invalid") from exc
        except (LookupError, PermissionError) as exc:
            raise HTTPException(status_code=404, detail="partner_not_available") from exc
        return {"proposal": asdict(draft), "outbound_sent": False, "advisory_only": True}

    @router.post("/business-workspace/commercial/partner-opportunities/rank", tags=["business-workspace"])
    async def rank_partner_opportunities(request: Request):
        """Owner-scoped partner shortlist with no outbound or new partner owner."""
        from application.partner.growth_advisory import PartnerOpportunity

        tenant, business = scope(request)
        if partner_registry is None:
            raise HTTPException(status_code=503, detail="canonical_partner_owner_unavailable")
        body = await json_body(request)
        if set(body) != {"candidates", "audience_terms"}:
            raise HTTPException(status_code=422, detail="partner_ranking_fields_invalid")
        candidates = body["candidates"]
        terms = body["audience_terms"]
        if (not isinstance(candidates, list) or len(candidates) > 100
                or not isinstance(terms, list) or len(terms) > 48
                or any(not isinstance(term, str) or len(term) > 100 for term in terms)):
            raise HTTPException(status_code=422, detail="partner_ranking_batch_invalid")
        allowed = {
            "partner_id", "name", "topics", "audience_summary", "recent_topic",
            "followers", "contact_basis", "contact_value", "source_url", "competitor",
        }
        try:
            rows = []
            for row in candidates:
                if not isinstance(row, dict) or not set(row) <= allowed:
                    raise ValueError("partner_candidate_fields_invalid")
                rows.append(PartnerOpportunity(
                    business_id=business, **{
                        **row, "topics": tuple(row.get("topics") or ()),
                    },
                ))
            ranked = partner_registry.assess_growth_opportunities(
                tenant_id=tenant, business_id=business,
                candidates=tuple(rows), audience_terms=tuple(terms),
            )
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="partner_candidate_invalid") from exc
        except (LookupError, PermissionError) as exc:
            raise HTTPException(status_code=404, detail="canonical_partner_not_found") from exc
        return {
            "tenant_id": tenant, "business_id": business,
            "advisory_only": True, "outbound_sent": False,
            "ranking": [asdict(value) for value in ranked],
        }

    @router.get("/business-workspace/commercial/funnel-metrics", tags=["business-workspace"])
    async def commercial_funnel_metrics(request: Request):
        """Read-only donor sales metrics from canonical Lead/Order/Invoice truth."""
        tenant, business = scope(request)
        leads = purchases.leads.list_for_business(tenant_id=tenant, business_id=business)
        statuses: dict[str, int] = {}
        for lead in leads:
            if lead.customer_id and lead.conversation_id and lead.channel:
                stage = str(lead.status or "new")
                statuses[stage] = statuses.get(stage, 0) + 1
        orders = [
            _order_status(purchases, tenant, business, order.order_id, checkout=checkout)
            for order in purchases.orders.list_for_business(tenant_id=tenant, business_id=business)
            if order.order_kind == "commercial_program"
        ]
        verified = [order for order in orders if order["provider_verified"]]
        gross: dict[str, int] = {}
        for order in verified:
            currency = order["currency"]
            gross[currency] = gross.get(currency, 0) + order["paid_minor"]
        return {
            "tenant_id": tenant,
            "business_id": business,
            "lead_count": sum(statuses.values()),
            "stages": statuses,
            "order_count": len(orders),
            "externally_verified_order_count": len(verified),
            "verified_gross_captured_minor_by_currency": gross,
            "net_revenue_not_computed": True,
            "external_payment_proof_required": True,
        }

    @router.post("/business-workspace/commercial/leads/{lead_id}/engagement-review", tags=["business-workspace"])
    async def review_sales_engagement(lead_id: str, request: Request):
        """Owner sees safe follow-up eligibility or canonical handoff signal.

        The read-only review does not send to a customer or persist approvals.
        """
        tenant, business = scope(request)
        if context_reader is None:
            raise HTTPException(status_code=503, detail="commercial_context_owner_not_configured")
        body = await json_body(request)
        fields = {
            "expected_fingerprint", "model_confidence", "human_requested",
            "sensitive_context", "pricing_exception", "negative_sentiment",
            "failed_attempts", "customer_opted_out",
        }
        if not set(body) <= fields or not {
            "expected_fingerprint", "model_confidence",
        } <= set(body):
            raise HTTPException(status_code=422, detail="commercial_engagement_fields_invalid")
        try:
            return context_reader.evaluate_sales_engagement(
                tenant_id=tenant, business_id=business, lead_id=lead_id,
                **body,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="commercial_lead_not_found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="commercial_engagement_input_invalid") from exc
        except RuntimeError as exc:
            if str(exc).startswith("commercial_context_"):
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            raise

    @router.get("/business-workspace/commercial/leads/{lead_id}/context", tags=["business-workspace"])
    async def read_commercial_context(lead_id: str, request: Request):
        tenant, business = scope(request)
        if context_reader is None:
            raise HTTPException(status_code=503, detail="commercial_context_owner_not_configured")
        try:
            return asdict(context_reader.read(
                tenant_id=tenant, business_id=business, lead_id=lead_id,
            ))
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="commercial_lead_not_found") from exc

    @router.get("/business-workspace/commercial/leads/{lead_id}/funnel-advisory", tags=["business-workspace"])
    async def read_commercial_funnel_advisory(lead_id: str, request: Request):
        tenant, business = scope(request)
        if context_reader is None:
            raise HTTPException(status_code=503, detail="commercial_context_owner_not_configured")
        try:
            return context_reader.read_funnel_advisory(
                tenant_id=tenant, business_id=business, lead_id=lead_id,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="commercial_lead_not_found") from exc

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
                result.append(_order_status(purchases, tenant, business, order.order_id, checkout=checkout))
        return {"orders": result}

    @router.get("/business-workspace/commercial/orders/{order_id}", tags=["business-workspace"])
    async def get_order(order_id: str, request: Request):
        tenant, business = scope(request)
        try:
            return _order_status(purchases, tenant, business, order_id, checkout=checkout)
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

    @router.post("/business-workspace/commercial/orders/{order_id}/reconcile", tags=["business-workspace"])
    async def reconcile_verified_payment(order_id: str, request: Request):
        tenant, business = scope(request)
        if settlement is None:
            raise HTTPException(status_code=503, detail="commercial_settlement_authority_unconfigured")
        body = await json_body(request)
        if body:
            raise HTTPException(status_code=422, detail="commercial_settlement_accepts_no_claimed_payment_fields")
        try:
            # The server-held verifier fetches authoritative PSP evidence;
            # client-supplied status, money or evidence can never create revenue.
            return asdict(settlement.reconcile(
                tenant_id=tenant, business_id=business, order_id=order_id,
            ))
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="commercial_order_not_found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc


def _order_status(purchases, tenant, business, order_id, *, checkout=None):
    order, link = purchases._read(tenant_id=tenant, business_id=business, order_id=order_id)
    invoice = purchases.invoices.get(tenant_id=tenant, business_id=business, invoice_id=link["invoice_id"])
    if (invoice.tenant_id != tenant or invoice.business_id != business
            or invoice.total_minor != link["amount_minor"]
            or invoice.currency != link["currency"]
            or dict(invoice.metadata).get("order_id") != order_id):
        raise RuntimeError("commercial_invoice_provenance_invalid")
    verified = False
    if checkout is not None and invoice.status.value == "paid":
        saved = checkout._saved(tenant_id=tenant, business_id=business, order_id=order_id)
        if saved is not None and (saved.invoice_id != invoice.invoice_id
                                  or saved.amount_minor != invoice.total_minor
                                  or saved.currency != invoice.currency):
            raise RuntimeError("commercial_checkout_invoice_provenance_invalid")
        if saved is not None:
            verified = purchases.invoices.has_verified_commercial_settlement(
                tenant_id=tenant, business_id=business, invoice_id=invoice.invoice_id,
                provider_name=saved.provider_name, external_reference=saved.external_reference,
            )
    return {
        "order_id": order_id, "status": order.lifecycle_status.value,
        "invoice_id": invoice.invoice_id, "invoice_status": invoice.status.value,
        "amount_minor": invoice.total_minor, "paid_minor": invoice.paid_minor,
        "currency": invoice.currency, "offer_id": link["offer_id"],
        "lead_id": link["lead_id"], "customer_id": link["customer_id"],
        "program_id": link["program_id"],
        "provider_verified": verified,
    }


__all__ = ["register_business_workspace_commercial_routes", "CANON_PHASE18_COMMERCIAL_OWNER_API"]
