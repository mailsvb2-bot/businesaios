from __future__ import annotations

from typing import TYPE_CHECKING

from runtime.messaging_policy.preference_loader import load_channel_preference as _load_channel_preference

__all__ = ["load_channel_preference"]

if TYPE_CHECKING:
    load_channel_preference = _load_channel_preference


def __getattr__(name: str):
    if name == "load_channel_preference":
        return _load_channel_preference
    raise AttributeError(name)
