"""Telegram policy package.

Keep package import side-effect light while preserving the historical public API.
Use lazy attribute resolution to avoid circular imports from product-domain policy
modules that only need helper functions.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["TelegramIngressPolicyV1", "UnifiedTelegramPolicyV3"]


def __getattr__(name: str) -> Any:
    if name == "TelegramIngressPolicyV1":
        return import_module("core.policies.telegram.ingress_policy").TelegramIngressPolicyV1
    if name == "UnifiedTelegramPolicyV3":
        return import_module("core.policies.telegram.unified_policy").UnifiedTelegramPolicyV3
    raise AttributeError(name)
