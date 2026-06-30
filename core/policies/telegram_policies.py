"""Telegram policies (facade).

This module is intentionally thin to avoid a "god file".
All real user-facing logic lives in core/policies/telegram/*.

Public API (kept stable for imports/tests):
- TelegramIngressPolicyV1
- UnifiedTelegramPolicyV3
"""

from __future__ import annotations

from core.policies.telegram import TelegramIngressPolicyV1, UnifiedTelegramPolicyV3

__all__ = ["TelegramIngressPolicyV1", "UnifiedTelegramPolicyV3"]

