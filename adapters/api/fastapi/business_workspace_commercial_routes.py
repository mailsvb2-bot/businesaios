"""Verified owner commercial API; uses the canonical order/invoice/offer owners."""
from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request

from adapters.api.fastapi.router_support import business_owner_scope, json_body
from contracts.customer import CustomerNotFound, CustomerStatus

CANON_PHASE18_COMMERCIAL_OWNER_API = True


def register_business_workspace_commercial_routes(*, router: APIRouter, auth_bundle, purchases, checkout=None, context_reader=None, settlement=None, partner_registry=None, provider_handlers=None, customers=None, scene_agent=None):
    def scope(request):
        _, tenant, business = business_owner_scope(request=request, auth_bundle=auth_bundle)
        return tenant, business

    @router.post("/business-workspace/commercial/advertising/creatives/prepare", tags=["business-workspace"])
    async def prepare_ad_creatives(request: Request):
        """Authenticated image/video creative variants; never generate or spend."""
        from application.visual_creative_semantics.phase18_advertising_studio import (
            prepare_advertising_creatives,
        )
        from core.growth.ads.creative.pipeline import visual_scene_breakdown
        from core.llm.agent import LLMTaskContext

        tenant, business = scope(request)
        body = await json_body(request)
        allowed = {"campaign_id", "headline", "description", "brand_context",
                   "campaign_goal", "kind", "formats", "country_code"}
        if not isinstance(body, dict) or set(body) != allowed - {"country_code"} and set(body) != allowed:
            raise HTTPException(status_code=422, detail="advertising_brief_fields_invalid")
        if not isinstance(body.get("formats"), list):
            raise HTTPException(status_code=422, detail="advertising_formats_invalid")
        request_text = f"{body.get('headline')}. {body.get('description')}"
        scene = await asyncio.to_thread(visual_scene_breakdown, scene_agent, LLMTaskContext(
            tenant_id=tenant, offer={"request": request_text}, correlation_key=f"ad-scene:{business}"), request_text)
        try:
            variants = prepare_advertising_creatives(
                tenant_id=tenant, business_id=business,
                campaign_id=body["campaign_id"], headline=body["headline"],
                description=body["description"], brand_context=body["brand_context"],
                campaign_goal=body["campaign_goal"], kind=body["kind"],
                formats=tuple(body["formats"]),
                country_code=body.get("country_code", ""), scene=scene,
            )
        except (TypeError, ValueError, AttributeError) as exc:
            raise HTTPException(status_code=422, detail="advertising_brief_invalid") from exc
        return {"tenant_id": tenant, "business_id": business,
                "draft_only": True, "generation_submitted": False,
                "campaign_launched": False, "spend_authorized": False,
                "creatives": [asdict(item) for item in variants]}

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

    @router.post("/business-workspace/commercial/leads/{lead_id}/approved-followups/{approval_id}/deliver", tags=["business-workspace"])
    async def deliver_approved_followup(lead_id: str, approval_id: str, request: Request):
        """Resume an archived, precisely bound human-approved commercial message.

        No independent sender or scheduler. Only the canonical provider approval
        resume can enqueue and observe a real provider result.
        """
        _, tenant, business = business_owner_scope(
            request=request, auth_bundle=auth_bundle,
            required_scope="provider_control_plane",
        )
        if context_reader is None or provider_handlers is None or customers is None:
            raise HTTPException(status_code=503, detail="canonical_followup_execution_unavailable")
        body = await json_body(request)
        if body:
            raise HTTPException(status_code=422, detail="approved_followup_accepts_no_mutable_payload")
        try:
            record = provider_handlers.approval_store_factory().get(approval_id)
            if record is None:
                raise LookupError("commercial_followup_approval_not_found")
            req = record.request
            if str(req.tenant_id) != tenant or str(getattr(record.status, "value", record.status)) != "approved":
                raise PermissionError("commercial_followup_approval_denied")
            metadata = dict(req.metadata or {})
            decision_id = str(metadata.get("decision_id") or "").strip()
            if not decision_id:
                raise PermissionError("commercial_followup_decision_missing")
            envelope = provider_handlers.decision_loader(
                tenant_id=tenant, decision_id=decision_id,
            )
            decision = getattr(envelope, "decision", None)
            if decision is None or getattr(decision, "decision_id", None) != decision_id:
                raise PermissionError("commercial_followup_archive_invalid")
            archived = dict(getattr(decision, "payload", None) or {})
            binding = archived.get("commercial_followup")
            if not isinstance(binding, dict) or any(
                binding.get(name) != expected
                for name, expected in (
                    ("tenant_id", tenant), ("business_id", business),
                    ("lead_id", lead_id),
                )
            ):
                raise PermissionError("commercial_followup_archive_scope_mismatch")
            current = context_reader.require_current(
                tenant_id=tenant, business_id=business, lead_id=lead_id,
                expected_fingerprint=str(binding.get("context_fingerprint") or ""),
            )
            if (binding.get("customer_id") != current.customer_id
                    or binding.get("conversation_id") != current.conversation_id
                    or binding.get("channel") != current.channel
                    or current.orders or current.inbound_message_count < 1
                    or current.sales_stage in {"lost", "closed", "do_not_contact"}):
                raise PermissionError("commercial_followup_identity_or_order_changed")
            approved_resume = metadata.get("approval_resume_context")
            if not isinstance(approved_resume, dict):
                raise PermissionError("commercial_followup_approved_payload_unbound")
            provider_key = str(approved_resume.get("provider_key") or "")
            provider_payload = approved_resume.get("payload")
            if not provider_key or not isinstance(provider_payload, dict):
                raise PermissionError("commercial_followup_payload_invalid")
            destinations = {
                "telegram_bot": ("telegram", ("chat_id", "user_id", "recipient")),
                "vk_messaging": ("vk", ("peer_id", "user_id")),
                "max_messaging": ("max", ("user_id", "chat_id")),
                "whatsapp_cloud": ("whatsapp", ("to", "user_id")),
                "email_connector": ("email", ("recipient", "to")),
            }
            if provider_key not in destinations:
                raise PermissionError("commercial_followup_provider_not_supported")
            channel, recipient_fields = destinations[provider_key]
            recipients = {
                str(provider_payload.get(field) or "").strip()
                for field in recipient_fields
                if str(provider_payload.get(field) or "").strip()
            }
            if channel != current.channel or len(recipients) != 1:
                raise PermissionError("commercial_followup_recipient_ambiguous")
            external_subject = next(iter(recipients))
            recipient_record = customers.find_by_identity(
                tenant_id=tenant, business_id=business,
                channel=channel, external_subject=external_subject,
            )
            if (recipient_record.customer.customer_id != current.customer_id
                    or recipient_record.customer.status is not CustomerStatus.ACTIVE):
                raise PermissionError("commercial_followup_recipient_not_customer")
            canonical_subject = {
                "provider_key": provider_key, "payload": provider_payload,
            }
            fingerprint = hashlib.sha256(json.dumps(
                canonical_subject, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False,
            ).encode("utf-8")).hexdigest()
            if binding.get("approved_provider_subject_sha256") != fingerprint:
                raise PermissionError("commercial_followup_approved_subject_mismatch")
            approved_business = provider_handlers.resolve_approved_message_business_id(
                tenant_id=tenant, approval_id=approval_id,
            )
            if approved_business != business:
                raise PermissionError("commercial_followup_provider_scope_mismatch")
            # Critical: do not accept customer text, recipient or provider payload
            # from this endpoint. The approval resume reads its archived subject.
            result = provider_handlers.resume_approved_message(
                tenant_id=tenant, approval_id=approval_id,
            )
            from application.business_autonomy.provider_delivery_truth import (
                provider_approval_completion_truth,
            )

            outcome = dict(result.get("execution") or {}).get("result") or {}
            delivered, ambiguous, terminal = provider_approval_completion_truth(
                provider_key=provider_key, result=outcome,
            )
            delivery_state = (
                "confirmed_delivered" if delivered else
                "ambiguous" if ambiguous else
                "terminal_non_delivery" if terminal else
                "queued_or_unconfirmed"
            )
            return {
                "tenant_id": tenant, "business_id": business, "lead_id": lead_id,
                "approval_id": approval_id, "canonical_provider_execution": result,
                "delivery_state": delivery_state,
                "delivery_confirmed": delivered,
                "delivery_status_from_provider_only": True,
            }
        except (LookupError, CustomerNotFound) as exc:
            raise HTTPException(status_code=404, detail="commercial_followup_not_found") from exc
        except (PermissionError, ValueError) as exc:
            raise HTTPException(status_code=403, detail="commercial_followup_denied") from exc
        except RuntimeError as exc:
            if str(exc).startswith("commercial_context_"):
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            raise HTTPException(status_code=409, detail="approved_followup_not_executable") from exc

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
                for currency in ("RUB", "XTR"):
                    try:
                        proof = purchases.priced_offer(
                            tenant_id=tenant, business_id=business, program_id=program_id,
                            offer_id=item.offer_id, currency=currency,
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
        required = {"lead_id", "customer_id", "program_id", "offer_id", "idempotency_key"}
        if (not required <= set(body) or set(body) - required - {"currency"}
                or not all(isinstance(x, str) for x in body.values())
                or body.get("currency", "RUB") not in {"RUB", "XTR"}):
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
