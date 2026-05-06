from __future__ import annotations

import importlib
from typing import Any


def _telegram_messaging_module():
    mod_name = "runtime._internal.effects_actions.telegram.messaging"
    return importlib.import_module(mod_name)


def send_message_effect(self, **kwargs: Any) -> Any:
    return _telegram_messaging_module().send_message_effect(self, **kwargs)
