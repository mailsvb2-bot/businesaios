from __future__ import annotations

from interfaces.web.common.http_response import HttpResponse
from interfaces.web.settings.alert_subscriptions.api_handlers import AlertSubscriptionsAPIHandlers
from interfaces.web.settings.alert_subscriptions.setting_key import SETTING_KEY
from interfaces.web.settings.common.save_command import SaveCommand
from interfaces.web.settings.common.settings_gateway_protocol import SettingsGateway


class SaveController:
    def __init__(self, *, settings_gateway: SettingsGateway, api_handlers: AlertSubscriptionsAPIHandlers | None = None):
        self._settings_gateway = settings_gateway
        self._api = api_handlers or AlertSubscriptionsAPIHandlers()

    def save(self, cmd: SaveCommand) -> HttpResponse:
        body = self._api.save_subscriptions(cmd.payload)
        self._settings_gateway.set_value(
            tenant_id=str(cmd.tenant_id),
            key=SETTING_KEY,
            value=list(body["saved_value"]),
        )
        return HttpResponse(
            status_code=200,
            content_type="application/json",
            body=body,
        )
