from __future__ import annotations

from typing import Any

from application.artifact import ArtifactRegistry
from application.asset import AssetRegistry
from application.business_constraint import BusinessConstraintRegistry
from application.business_goal import BusinessGoalRegistry
from application.business_resource import BusinessResourceRegistry
from application.business_service import BusinessServiceRegistry
from application.campaign.registry import CampaignRegistry
from application.deal import DealRegistry
from application.document import DocumentRegistry
from application.employee import EmployeeRegistry
from application.expense import ExpenseRegistry
from application.lead import LeadRegistry
from application.opportunity import OpportunityRegistry
from application.organization import OrganizationRegistry
from application.partner import PartnerRegistry
from application.person import PersonRegistry
from application.risk import RiskRegistry
from application.task import DurableTaskRegistry
from billing.invoice_registry import InvoiceRegistry
from crm import CustomerRegistry
from runtime.messaging.conversation_registry import ConversationRegistry

CANON_BUSINESS_ONTOLOGY_RUNTIME_WIRING = True


def wire_business_ontology_runtime(
    *,
    service: Any,
    event_store: Any | None,
    idempotency_store: Any,
    pii_vault: Any,
) -> Any | None:
    """Attach canonical ontology owners to one guarded service composition.

    This module owns wiring only. Entity semantics and durable writes remain in
    their registries; all event-sourced entities share the supplied EventStore.
    """
    bindings: dict[str, Any | None] = {
        "_organization_registry": None,
        "_lead_registry": None,
        "_person_registry": None,
        "_employee_registry": None,
        "_partner_registry": None,
        "_business_constraint_registry": None,
        "_business_goal_registry": None,
        "_business_resource_registry": None,
        "_business_service_registry": None,
        "_task_registry": None,
        "_artifact_registry": None,
        "_asset_registry": None,
        "_document_registry": None,
        "_deal_registry": None,
        "_campaign_registry": None,
        "_opportunity_registry": None,
        "_invoice_registry": None,
        "_expense_registry": None,
        "_risk_registry": None,
        "_conversation_registry": None,
    }
    customer_registry: Any | None = None
    if event_store is not None:
        customer_registry = CustomerRegistry(
            event_store=event_store,
            idempotency_store=idempotency_store,
            pii_vault=pii_vault,
        )
        bindings = {
            "_organization_registry": OrganizationRegistry(event_store=event_store, idempotency_store=idempotency_store),
            "_lead_registry": LeadRegistry(event_store=event_store, idempotency_store=idempotency_store),
            "_person_registry": PersonRegistry(event_store=event_store, idempotency_store=idempotency_store),
            "_employee_registry": EmployeeRegistry(event_store=event_store, idempotency_store=idempotency_store),
            "_partner_registry": PartnerRegistry(event_store=event_store, idempotency_store=idempotency_store),
            "_business_constraint_registry": BusinessConstraintRegistry(event_store=event_store, idempotency_store=idempotency_store),
            "_business_goal_registry": BusinessGoalRegistry(event_store=event_store, idempotency_store=idempotency_store),
            "_business_resource_registry": BusinessResourceRegistry(event_store=event_store, idempotency_store=idempotency_store),
            "_business_service_registry": BusinessServiceRegistry(event_store=event_store, idempotency_store=idempotency_store),
            "_task_registry": DurableTaskRegistry(event_store=event_store, idempotency_store=idempotency_store),
            "_artifact_registry": ArtifactRegistry(event_store=event_store, idempotency_store=idempotency_store),
            "_asset_registry": AssetRegistry(event_store=event_store, idempotency_store=idempotency_store),
            "_document_registry": DocumentRegistry(event_store=event_store, idempotency_store=idempotency_store),
            "_deal_registry": DealRegistry(event_store=event_store, idempotency_store=idempotency_store),
            "_campaign_registry": CampaignRegistry(event_store=event_store, idempotency_store=idempotency_store),
            "_opportunity_registry": OpportunityRegistry(event_store=event_store, idempotency_store=idempotency_store),
            "_invoice_registry": InvoiceRegistry(event_store=event_store, idempotency_store=idempotency_store),
            "_expense_registry": ExpenseRegistry(event_store=event_store, idempotency_store=idempotency_store),
            "_risk_registry": RiskRegistry(event_store=event_store, idempotency_store=idempotency_store),
            "_conversation_registry": ConversationRegistry(
                event_store=event_store,
                idempotency_store=idempotency_store,
                customer_registry=customer_registry,
            ),
        }
    for attribute, registry in bindings.items():
        setattr(service, attribute, registry)
    return customer_registry


__all__ = [
    "CANON_BUSINESS_ONTOLOGY_RUNTIME_WIRING",
    "wire_business_ontology_runtime",
]
