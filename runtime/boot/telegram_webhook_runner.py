"""Thin boot adapter for the Telegram webhook runtime owner."""

from __future__ import annotations

from runtime.boot_impl.telegram_webhook_runner import *  # noqa: F401,F403
from runtime.boot_impl.telegram_webhook_runner import __all__ as __all__

CANON_BOOT_WIRING_ONLY = True
CANON_TELEGRAM_WEBHOOK_RUNNER_ADAPTER = True
