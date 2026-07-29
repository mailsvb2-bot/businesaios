"""Thin boot adapter for the Telegram long-poll runtime owner."""

from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True
CANON_TELEGRAM_RUNNER_ADAPTER = True

from runtime.boot_impl.telegram_runner import *  # noqa: F401,F403
from runtime.boot_impl.telegram_runner import __all__
