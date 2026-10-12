"""A single canonical sales lead per verified customer + conversation.

The provider webhook is already signature-checked and deduplicated before
this bridge runs. No independent customer/lead/CRM state or raw PII cache.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from contracts.customer import CustomerStatus
from contracts.lead import LeadLifecycleStatus, LeadNotFound
from contracts.messaging_event_identity import MessageDirection
from runtime.messaging.conversation_registry import ConversationLifecycleStatus
from runtime.messaging.message_registry import MessageLifecycleStatus

CANON_COMMERCIAL_INGRESS = True


@dataclass(frozen=True)
class CommercialIngressReceipt:
    lead_id: str
    customer_id: str
    conversation_id: str
    message_id: str
    channel: str
    sales_stage: str


class CommercialIngressCoordinator:
    """Read existing canonical facts, write ONLY through LeadRegistry."""

    def __init__(self, *, customers, conversations, messages, leads):
        self._customers = customers
        self._conversations = conversations
        self._messages = messages
        self._leads = leads

    @staticmethod
    def lead_identity(*, tenant_id: str, business_id: str,
                      customer_id: str, conversation_id: str) -> str:
        if not all((tenant_id, business_id, customer_id, conversation_id)):
            raise ValueError("commercial_ingress_identity_required")
        return str(uuid5(
            NAMESPACE_URL, ":".join(("businessaios", "sales-lead", tenant_id,
                                     business_id, customer_id, conversation_id)),
        ))

    def ensure_verified_ingress(self, *, tenant_id: str, business_id: str,
                                customer_id: str, conversation_id: str,
                                message_id: str, channel: str) -> CommercialIngressReceipt:
        if not all(isinstance(v, str) and v.strip() for v in (
            tenant_id, business_id, customer_id, conversation_id, message_id, channel,
        )):
            raise ValueError("commercial_ingress_missing_canonical_identity")
        customer = self._customers.get_customer(
            tenant_id=tenant_id, business_id=business_id, customer_id=customer_id,
        ).customer
        conversation = self._conversations.get(
            tenant_id=tenant_id, business_id=business_id, conversation_id=conversation_id,
        )
        message = self._messages.get(
            tenant_id=tenant_id, business_id=business_id, message_id=message_id,
        )
        if (customer.customer_id != customer_id or customer.status is not CustomerStatus.ACTIVE
                or conversation.customer_id != customer_id
                or conversation.lifecycle_status is not ConversationLifecycleStatus.OPEN
                or conversation.channel != channel
                or message.customer_id != customer_id
                or message.conversation_id != conversation_id
                or message.channel != channel
                or message.direction is not MessageDirection.INBOUND
                or message.lifecycle_status is not MessageLifecycleStatus.RECORDED):
            raise ValueError("commercial_ingress_canonical_binding_mismatch")
        lead_id = self.lead_identity(
            tenant_id=tenant_id, business_id=business_id,
            customer_id=customer_id, conversation_id=conversation_id,
        )
        try:
            lead = self._leads.get(
                tenant_id=tenant_id, business_id=business_id, lead_id=lead_id,
            )
        except LeadNotFound:
            lead = self._leads.create(
                tenant_id=tenant_id, business_id=business_id, lead_id=lead_id,
                source=channel, status="new", customer_id=customer_id,
                conversation_id=conversation_id, channel=channel,
                idempotency_key="commercial-ingress:" + lead_id,
            )
        if (lead.tenant_id != tenant_id or lead.business_id != business_id
                or lead.customer_id != customer_id
                or lead.conversation_id != conversation_id or lead.channel != channel
                or lead.source != channel):
            raise ValueError("commercial_lead_scope_or_identity_conflict")
        if lead.lifecycle_status is LeadLifecycleStatus.ARCHIVED:
            raise ValueError("commercial_lead_archived_no_automatic_reopening")
        return CommercialIngressReceipt(
            lead_id=lead_id, customer_id=customer_id, conversation_id=conversation_id,
            message_id=message_id, channel=channel, sales_stage=lead.status or "new",
        )


__all__ = ["CANON_COMMERCIAL_INGRESS",
           "CommercialIngressCoordinator", "CommercialIngressReceipt"]
