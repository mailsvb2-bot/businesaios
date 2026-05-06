from __future__ import annotations

from interfaces.web.common.http_response import HttpResponse
from interfaces.web.settings.alert_subscriptions.api_handlers import AlertSubscriptionsAPIHandlers
from interfaces.web.settings.alert_subscriptions.setting_key import SETTING_KEY
from interfaces.web.settings.common.page_query import PageQuery
from interfaces.web.settings.common.settings_gateway_protocol import SettingsGateway


class PageController:
    def __init__(self, *, settings_gateway: SettingsGateway, api_handlers: AlertSubscriptionsAPIHandlers | None = None):
        self._settings_gateway = settings_gateway
        self._api = api_handlers or AlertSubscriptionsAPIHandlers()

    def get_model(self, query: PageQuery) -> HttpResponse:
        tenant_id = str(query.tenant_id)
        existing_value = self._settings_gateway.get_value(tenant_id=tenant_id, key=SETTING_KEY)
        body = self._api.get_page_model(existing_value, tenant_id=tenant_id)
        return HttpResponse(
            status_code=200,
            content_type="application/json",
            body=body,
        )
