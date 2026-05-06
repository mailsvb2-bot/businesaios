from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from interfaces.web.settings.messaging_preferences.form_parser import parse_preference_form
from runtime.messaging.settings import SETTING_KEY


@dataclass(frozen=True)
class SaveResult:
    setting_key: str
    saved_value: dict[str, Any]


class MessagingPreferencesService:
    def save(self, payload: Mapping[str, Any]) -> SaveResult:
        value = parse_preference_form(payload)
        return SaveResult(
            setting_key=SETTING_KEY,
            saved_value=value,
        )
