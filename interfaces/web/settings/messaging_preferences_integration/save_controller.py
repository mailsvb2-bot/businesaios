from __future__ import annotations

from interfaces.web.common.http_response import HttpResponse
from interfaces.web.settings.common.save_command import SaveCommand
from interfaces.web.settings.common.settings_gateway_protocol import SettingsGateway
from interfaces.web.settings.messaging_preferences.api_handlers import MessagingPreferencesAPIHandlers
from runtime.messaging.settings import SETTING_KEY


class SaveController:
    def __init__(self, *, settings_gateway: SettingsGateway, api_handlers: MessagingPreferencesAPIHandlers | None = None):
        self._settings_gateway = settings_gateway
        self._api = api_handlers or MessagingPreferencesAPIHandlers()

    def save(self, cmd: SaveCommand) -> HttpResponse:
        body = self._api.save_preferences(cmd.payload)
        self._settings_gateway.set_value(
            tenant_id=str(cmd.tenant_id),
            key=SETTING_KEY,
            value=dict(body["saved_value"]),
        )
        return HttpResponse(
            status_code=200,
            content_type="application/json",
            body=body,
        )
