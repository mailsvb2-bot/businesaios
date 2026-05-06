from __future__ import annotations

from interfaces.web.settings.alert_subscriptions.page_dict import page_to_dict
from interfaces.web.settings.alert_subscriptions.page_presenter import present_page
from interfaces.web.settings.alert_subscriptions.service import AlertSubscriptionsService


class AlertSubscriptionsAPIHandlers:
    def __init__(self, *, service: AlertSubscriptionsService | None = None):
        self._service = service or AlertSubscriptionsService()

    def get_page_model(self, existing_value, *, tenant_id: str) -> dict:
        return page_to_dict(present_page(existing_value, tenant_id=str(tenant_id)))

    def save_subscriptions(self, payload) -> dict:
        result = self._service.save(payload)
        return {
            "setting_key": result.setting_key,
            "saved_value": result.saved_value,
        }
