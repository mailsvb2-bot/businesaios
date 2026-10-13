"""Read-only, PII-free commercial context projected from canonical owners.

This is NOT a second sales state machine or persistent AI memory. Every read
projects current Lead/Customer/Conversation/Message/Order/Billing facts, and
returns a fingerprint that detects stale model plans before any execution.
An invoice marked PAID is never mistaken for an externally verified payment.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from contracts.customer import CustomerStatus
from contracts.lead import LeadLifecycleStatus
from contracts.messaging_event_identity import MessageDirection
from runtime.messaging.conversation_registry import ConversationLifecycleStatus

CANON_PHASE18_COMMERCIAL_CONTEXT_PROJECTION = True


@dataclass(frozen=True)
class CommercialOrderSummary:
    order_id: str
    invoice_id: str
    program_id: str
    offer_id: str
    amount_minor: int
    paid_minor: int
    currency: str
    billing_status: str
    order_status: str
    external_payment_verified: bool = False
    delivery_verified: bool = False


@dataclass(frozen=True)
class CommercialJourneyContext:
    tenant_id: str
    business_id: str
    lead_id: str
    customer_id: str
    conversation_id: str
    channel: str
    sales_stage: str
    lead_active: bool
    customer_active: bool
    conversation_open: bool
    inbound_message_count: int
    latest_message_id: str | None
    active_program_ids: tuple[str, ...]
    orders: tuple[CommercialOrderSummary, ...]
    context_fingerprint: str

    @property
    def can_prepare_offer(self) -> bool:
        return self.lead_active and self.customer_active and self.conversation_open


class CommercialJourneyContextReader:
    """No writes, no plaintext PII, no invented payments or inferred revenue."""

    def __init__(self, *, leads: Any, customers: Any, conversations: Any,
                 messages: Any, programs: Any, orders: Any, invoices: Any) -> None:
        self._leads, self._customers = leads, customers
        self._conversations, self._messages = conversations, messages
        self._programs, self._orders, self._invoices = programs, orders, invoices

    def read(self, *, tenant_id: str, business_id: str,
             lead_id: str) -> CommercialJourneyContext:
        lead = self._leads.get(tenant_id=tenant_id, business_id=business_id, lead_id=lead_id)
        if (lead.tenant_id != tenant_id or lead.business_id != business_id
                or not lead.customer_id or not lead.conversation_id or not lead.channel):
            raise ValueError("commercial_context_lead_unbound")
        record = self._customers.get_customer(
            tenant_id=tenant_id, business_id=business_id, customer_id=lead.customer_id,
        )
        customer = record.customer
        conversation = self._conversations.get(
            tenant_id=tenant_id, business_id=business_id,
            conversation_id=lead.conversation_id,
        )
        if (customer.customer_id != lead.customer_id
                or conversation.customer_id != lead.customer_id
                or conversation.channel != lead.channel):
            raise RuntimeError("commercial_context_canonical_identity_mismatch")
        rows = [
            item for item in self._messages.list_for_business(
                tenant_id=tenant_id, business_id=business_id,
            )
            if item.customer_id == lead.customer_id
            and item.conversation_id == lead.conversation_id
            and item.channel == lead.channel
        ]
        rows.sort(key=lambda item: (item.created_at_ms, item.message_id))
        active_programs = tuple(sorted(
            str(program["id"])
            for program in self._programs.list_for_business(
                tenant_id=tenant_id, business_id=business_id, limit=50,
            )
            if program.get("status") == "active"
        ))
        linked_orders: list[CommercialOrderSummary] = []
        for order in self._orders.list_for_business(
            tenant_id=tenant_id, business_id=business_id,
        ):
            if order.order_kind != "commercial_program":
                continue
            ref = self._orders.get_order_specialization(
                order_id=order.order_id, tenant_id=tenant_id, business_id=business_id,
            )
            if ref.get("lead_id") != lead_id:
                continue
            if ref.get("customer_id") != lead.customer_id:
                raise RuntimeError("commercial_context_order_customer_mismatch")
            invoice = self._invoices.get(
                tenant_id=tenant_id, business_id=business_id,
                invoice_id=str(ref["invoice_id"]),
            )
            invoice.validate()
            if (invoice.tenant_id != tenant_id or invoice.business_id != business_id
                    or invoice.invoice_id != ref["invoice_id"]
                    or dict(invoice.metadata).get("order_id") != order.order_id
                    or invoice.total_minor != ref["amount_minor"]
                    or invoice.currency != ref["currency"]):
                raise RuntimeError("commercial_context_order_invoice_mismatch")
            linked_orders.append(CommercialOrderSummary(
                order_id=order.order_id,
                invoice_id=invoice.invoice_id,
                program_id=str(ref["program_id"]),
                offer_id=str(ref["offer_id"]),
                amount_minor=invoice.total_minor,
                paid_minor=invoice.paid_minor,
                currency=invoice.currency,
                billing_status=invoice.status.value,
                order_status=order.lifecycle_status.value,
            ))
        linked_orders.sort(key=lambda item: item.order_id)
        canonical = {
            "tenant_id": tenant_id, "business_id": business_id, "lead_id": lead_id,
            "customer_id": lead.customer_id, "conversation_id": lead.conversation_id,
            "channel": lead.channel, "stage": lead.status or "new",
            "lead_updated_at_ms": lead.updated_at_ms,
            "lead_status": lead.lifecycle_status.value,
            "customer_status": customer.status.value,
            "customer_updated_at_ms": customer.updated_at_ms,
            "conversation_status": conversation.lifecycle_status.value,
            "conversation_updated_at_ms": conversation.updated_at_ms,
            "messages": [(item.message_id, item.created_at_ms, item.direction.value, item.lifecycle_status.value)
                         for item in rows],
            "active_program_ids": active_programs,
            "orders": [item.__dict__ for item in linked_orders],
        }
        digest = hashlib.sha256(json.dumps(
            canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        return CommercialJourneyContext(
            tenant_id=tenant_id, business_id=business_id, lead_id=lead_id,
            customer_id=lead.customer_id, conversation_id=lead.conversation_id,
            channel=lead.channel, sales_stage=lead.status or "new",
            lead_active=lead.lifecycle_status is LeadLifecycleStatus.ACTIVE,
            customer_active=customer.status is CustomerStatus.ACTIVE,
            conversation_open=conversation.lifecycle_status is ConversationLifecycleStatus.OPEN,
            inbound_message_count=sum(1 for item in rows if item.direction is MessageDirection.INBOUND),
            latest_message_id=rows[-1].message_id if rows else None,
            active_program_ids=active_programs,
            orders=tuple(linked_orders),
            context_fingerprint=digest,
        )

    def read_funnel_advisory(self, *, tenant_id: str, business_id: str,
                             lead_id: str) -> dict[str, Any]:
        """Evidence-only stage projection; never makes sales or PSP decisions."""
        from advisory.funnel_intelligence import (
            CommercialEvidence,
            derive_conversation_stage,
        )

        snapshot = self.read(
            tenant_id=tenant_id, business_id=business_id, lead_id=lead_id,
        )
        # Invoices are intentionally excluded as payment proof here:
        # canonical Billing settlement may exist without verified PSP capture.
        checkout_found = bool(snapshot.orders)
        evidence = CommercialEvidence(
            inbound_seen=snapshot.inbound_message_count > 0,
            contact_seen=snapshot.customer_active,
            need_captured=snapshot.sales_stage in {
                "need_known", "qualified", "offer_presented",
            },
            qualified=snapshot.sales_stage in {"qualified", "offer_presented"},
            offer_presented=snapshot.sales_stage == "offer_presented",
            checkout_requested=checkout_found,
            checkout_created=False,
            payment_confirmed=False,
            declined=snapshot.sales_stage == "lost",
        )
        stage = derive_conversation_stage(evidence)
        return {
            "tenant_id": snapshot.tenant_id,
            "business_id": snapshot.business_id,
            "lead_id": snapshot.lead_id,
            "context_fingerprint": snapshot.context_fingerprint,
            "derived_stage": stage.value,
            "has_order": checkout_found,
            "externally_verified_payment": False,
            "advisory_only": True,
            "can_prepare_offer": snapshot.can_prepare_offer,
        }

    def evaluate_sales_engagement(
        self, *, tenant_id: str, business_id: str, lead_id: str,
        expected_fingerprint: str, model_confidence: float,
        human_requested: bool = False, sensitive_context: bool = False,
        pricing_exception: bool = False, negative_sentiment: bool = False,
        failed_attempts: int = 0, customer_opted_out: bool = False,
    ) -> dict[str, Any]:
        """Donor sales-handoff and follow-up policy over canonical facts only.

        Advisory only: no provider sends, queue writes, or duplicate scheduler.
        The canonical send owner must recheck context and consent separately.
        """
        import math

        from execution.canonical_operator_handoff import canonical_operator_handoff

        snapshot = self.require_current(
            tenant_id=tenant_id, business_id=business_id, lead_id=lead_id,
            expected_fingerprint=expected_fingerprint,
        )
        flags = (human_requested, sensitive_context, pricing_exception,
                 negative_sentiment, customer_opted_out)
        if any(type(flag) is not bool for flag in flags):
            raise ValueError("sales_engagement_invalid_flags")
        if (type(model_confidence) not in (float, int)
                or not math.isfinite(model_confidence)
                or not 0 <= model_confidence <= 1):
            raise ValueError("sales_engagement_invalid_confidence")
        if type(failed_attempts) is not int or not 0 <= failed_attempts <= 100:
            raise ValueError("sales_engagement_invalid_attempts")
        reason, priority = None, None
        if sensitive_context:
            reason, priority = "sensitive_context", "urgent"
        elif human_requested:
            reason, priority = "explicit_human_request", "high"
        elif pricing_exception:
            reason, priority = "pricing_exception", "high"
        elif failed_attempts >= 2:
            reason, priority = "repeated_failure", "high"
        elif negative_sentiment:
            reason, priority = "negative_sentiment", "normal"
        elif model_confidence < 0.72:
            reason, priority = "low_confidence", "normal"
        blocked = (customer_opted_out or not snapshot.can_prepare_offer
                   or snapshot.sales_stage in {"lost", "closed", "do_not_contact"})
        has_order = bool(snapshot.orders)
        followup = (not blocked and reason is None and not has_order
                    and snapshot.inbound_message_count > 0)
        handoff = None
        if reason and not customer_opted_out:
            handoff = canonical_operator_handoff({
                "run_id": f"sales:{tenant_id}:{business_id}:{lead_id}",
                "decision_id": snapshot.context_fingerprint,
                "action": "commercial_sales_review",
                "handoff_reason": reason, "reason": reason,
                "handoff_state": "awaiting_operator",
                "approval_required": True,
                "blocked_by_policy": blocked or sensitive_context,
                "autonomy_tier": "supervised",
            })
        return {
            "tenant_id": tenant_id, "business_id": business_id,
            "lead_id": lead_id, "context_fingerprint": snapshot.context_fingerprint,
            "handoff": handoff, "handoff_priority": priority,
            "handoff_reason": reason,
            "outreach_suppressed": blocked or reason is not None or has_order,
            "suppression_reason": (
                "customer_opt_out" if customer_opted_out else
                "party_or_conversation_inactive" if blocked else
                "operator_review_required" if reason else
                "existing_order_requires_billing_truth" if has_order else None
            ),
            "followup_candidate": followup,
            "followup_queued": False, "message_sent": False,
            "operator_handoff_persisted": False,
            "manual_approval_required": True,
        }

    def require_current(self, *, tenant_id: str, business_id: str,
                        lead_id: str, expected_fingerprint: str) -> CommercialJourneyContext:
        snapshot = self.read(
            tenant_id=tenant_id, business_id=business_id, lead_id=lead_id,
        )
        if (not isinstance(expected_fingerprint, str)
                or expected_fingerprint != snapshot.context_fingerprint):
            raise RuntimeError("commercial_context_stale_decision")
        if not snapshot.can_prepare_offer:
            raise RuntimeError("commercial_context_customer_or_conversation_closed")
        return snapshot


__all__ = ["CANON_PHASE18_COMMERCIAL_CONTEXT_PROJECTION",
           "CommercialOrderSummary", "CommercialJourneyContext",
           "CommercialJourneyContextReader"]
