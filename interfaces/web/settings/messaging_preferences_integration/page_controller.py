from __future__ import annotations

from interfaces.web.common.http_response import HttpResponse
from interfaces.web.settings.common.page_query import PageQuery
from interfaces.web.settings.common.settings_gateway_protocol import SettingsGateway
from interfaces.web.settings.messaging_preferences.api_handlers import MessagingPreferencesAPIHandlers
from runtime.messaging.settings import SETTING_KEY


class PageController:
    def __init__(self, *, settings_gateway: SettingsGateway, api_handlers: MessagingPreferencesAPIHandlers | None = None):
        self._settings_gateway = settings_gateway
        self._api = api_handlers or MessagingPreferencesAPIHandlers()

    def get_model(self, query: PageQuery) -> HttpResponse:
        existing_value = self._settings_gateway.get_value(
            tenant_id=str(query.tenant_id),
            key=SETTING_KEY,
        )
        body = self._api.get_page_model(existing_value)
        return HttpResponse(
            status_code=200,
            content_type="application/json",
            body=body,
        )
