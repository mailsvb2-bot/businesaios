from __future__ import annotations

from app.web.components.client_outcome_dashboard_card import ClientOutcomeDashboardCard
from app.web.pages.client_outcomes import ClientOutcomesPage


def test_client_outcome_dashboard_card() -> None:
    payload = ClientOutcomeDashboardCard().build({'tenant_id': 'tenant-1', 'requested_clients': 10, 'billable_clients': 4, 'gross_revenue': 240.0})
    assert payload['kind'] == 'client_outcome_dashboard_card'
    assert payload['payload']['requested_clients'] == 10


def test_client_outcomes_page_build() -> None:
    payload = ClientOutcomesPage().build({'tenant_id': 'tenant-1', 'overview': {'requested_clients': 5, 'billable_clients': 2}})
    assert payload['kind'] == 'client_outcomes_page'
    assert payload['payload']['overview']['payload']['billable_clients'] == 2
