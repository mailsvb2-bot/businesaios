from __future__ import annotations

from typing import Any, Mapping

from interfaces.web.settings.messaging_preferences.page_dict import page_to_dict
from interfaces.web.settings.messaging_preferences.page_presenter import present_page
from interfaces.web.settings.messaging_preferences.service import MessagingPreferencesService


class MessagingPreferencesAPIHandlers:
    def __init__(self, *, service: MessagingPreferencesService | None = None):
        self._service = service or MessagingPreferencesService()

    def get_page_model(self, existing_value: Any) -> dict:
        return page_to_dict(present_page(existing_value))

    def save_preferences(self, payload: Mapping[str, Any]) -> dict:
        result = self._service.save(payload)
        return {
            "setting_key": result.setting_key,
            "saved_value": result.saved_value,
        }
