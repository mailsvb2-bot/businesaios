from __future__ import annotations

from dataclasses import dataclass

from admin.client_outcome_control_plane_models import ClientOutcomeAdminSummary, ClientOutcomeAdminWidgetPayload
from billing.client_outcome_dispute_service import ClientOutcomeDisputeService
from economics.client_outcome_economic_snapshot import ClientOutcomeEconomicSnapshot
from lead_outcomes.client_outcome_contract import ClientOutcomeOrder

CANON_CLIENT_OUTCOME_CONTROL_PLANE_SERVICE = True


@dataclass(frozen=True, slots=True)
class ClientOutcomeControlPlaneService:
    dispute_service: ClientOutcomeDisputeService

    def build_summary(self, *, order: ClientOutcomeOrder, economic_snapshot: ClientOutcomeEconomicSnapshot) -> ClientOutcomeAdminSummary:
        disputes = self.dispute_service.list_order_disputes(tenant_id=order.tenant_id, order_id=order.order_id)
        reversals = self.dispute_service.list_order_reversals(tenant_id=order.tenant_id, order_id=order.order_id)
        reversed_clients = len(reversals)
        reversal_amount = round(sum(float(item.get('amount', 0.0)) for item in reversals), 2)
        gross_revenue = round(float(economic_snapshot.billed_revenue), 2)
        return ClientOutcomeAdminSummary(
            tenant_id=order.tenant_id,
            business_id=order.business_id,
            order_id=order.order_id,
            package_id=order.package.package_id,
            requested_clients=order.package.requested_clients,
            verified_clients=economic_snapshot.verified_clients,
            billable_clients=economic_snapshot.billable_clients,
            reversed_clients=reversed_clients,
            open_disputes=sum(1 for item in disputes if item.get('status') in {'open', 'under_review'}),
            reversed_disputes=sum(1 for item in disputes if item.get('status') == 'reversed'),
            gross_revenue=gross_revenue,
            net_revenue=round(gross_revenue - reversal_amount, 2),
            currency=economic_snapshot.currency,
        )

    def build_widgets(self, *, summary: ClientOutcomeAdminSummary) -> tuple[ClientOutcomeAdminWidgetPayload, ...]:
        return (
            ClientOutcomeAdminWidgetPayload(widget_id='client_outcome_progress', kind='stat_block', payload={'requested_clients': summary.requested_clients, 'billable_clients': summary.billable_clients, 'reversed_clients': summary.reversed_clients}),
            ClientOutcomeAdminWidgetPayload(widget_id='client_outcome_disputes', kind='stat_block', payload={'open_disputes': summary.open_disputes, 'reversed_disputes': summary.reversed_disputes}),
            ClientOutcomeAdminWidgetPayload(widget_id='client_outcome_revenue', kind='stat_block', payload={'gross_revenue': summary.gross_revenue, 'net_revenue': summary.net_revenue, 'currency': summary.currency}),
        )
