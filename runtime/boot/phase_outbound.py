from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True


import logging
from typing import Any

from runtime.boot.boot_helpers import _emit_system_event, _env, _env_bool, _env_csv_tuple, _env_float, _env_int
from runtime.boot.outbound_constructor import build_with_supported_kwargs
from runtime.events import EventLog
from runtime.observability import log_exception_throttled

LOGGER = logging.getLogger(__name__)


def build_telegram_outbound_queue(*, settings: Any, event_log: EventLog, logging_mod: Any):
    """Build optional Telegram outbound queue.

    This module owns all outbound boot-time branching so boot_phases.py stays
    a phase index rather than a secondary implementation surface.
    """
    telegram_outbound_queue = None
    try:
        mode = str(_env("TELEGRAM_OUTBOUND_MODE", "async") or "async").strip().lower()
        tgs = settings.telegram

        if mode == "async":
            from interfaces.telegram.outbound.async_outbound_adapter import AsyncTelegramOutboundQueueAdapter

            telegram_outbound_queue = AsyncTelegramOutboundQueueAdapter(
                global_rps=float(tgs.outbound_global_rps),
                global_burst=int(tgs.outbound_global_burst),
                chat_rps=float(tgs.outbound_chat_rps),
                chat_burst=int(tgs.outbound_chat_burst),
                maxsize=int(tgs.outbound_queue_max),
                auto_start=True,
            )
            telegram_outbound_queue.start()
            return telegram_outbound_queue

        from interfaces.telegram.outbound.outbound_queue import TelegramOutboundQueue

        alert_ux_p95 = _env_float("OUTBOUND_ALERT_UX_P95_WAIT_MS", 0.0)
        alert_drop = _env_bool("OUTBOUND_ALERT_DROP_BEST_EFFORT", True)
        alert_qsize = _env_int("OUTBOUND_ALERT_QSIZE", 0)
        alert_min_interval = _env_float("OUTBOUND_ALERT_MIN_INTERVAL_S", 60.0)
        sh_enabled = _env_bool("OUTBOUND_SELF_HEAL_ENABLED", False)
        sh_cooldown = _env_float("OUTBOUND_SELF_HEAL_MARKETING_COOLDOWN_S", 60.0)
        sh_on_sla = _env_bool("OUTBOUND_SELF_HEAL_ON_SLA", True)
        sh_on_qsize = _env_bool("OUTBOUND_SELF_HEAL_ON_QSIZE", True)
        sh_on_drops = _env_bool("OUTBOUND_SELF_HEAL_ON_DROPS", False)
        purge_enabled = _env_bool("OUTBOUND_PURGE_ENABLED", True)
        purge_max_items = _env_int("OUTBOUND_PURGE_MAX_ITEMS", 10000)
        purge_blacklist = _env_csv_tuple("OUTBOUND_PURGE_BLACKLIST", ("marketing", "bulk", "analytics"))
        purge_whitelist = _env_csv_tuple("OUTBOUND_PURGE_WHITELIST", ("ux", "system", "payments"))

        base_kwargs = dict(
            global_rps=float(tgs.outbound_global_rps),
            global_burst=int(tgs.outbound_global_burst),
            chat_rps=float(tgs.outbound_chat_rps),
            chat_burst=int(tgs.outbound_chat_burst),
            max_queue=int(tgs.outbound_queue_max),
            warn_queue=int(tgs.outbound_warn_queue),
            emit_event=lambda et, pl: _emit_system_event(event_log, et, pl),
            log=logging_mod.getLogger("runtime.telegram.outbound"),
            overflow_policy=(
                "degrade"
                if str(_env("ENV", "dev") or "dev").strip().lower() in {"prod", "production"}
                and str(getattr(tgs, "outbound_overflow_policy", "block") or "block").strip().lower() == "block"
                else str(getattr(tgs, "outbound_overflow_policy", "block") or "block")
            ),
        )

        telegram_outbound_queue = build_with_supported_kwargs(
            constructor=TelegramOutboundQueue,
            kwargs={
                **base_kwargs,
                'alert_ux_wait_p95_ms': float(alert_ux_p95),
                'alert_drop_best_effort': bool(alert_drop),
                'alert_qsize': int(alert_qsize),
                'alert_min_interval_s': float(alert_min_interval),
                'metrics_logger': logging_mod.getLogger("runtime.telegram.outbound").warning,
                'self_heal_enabled': bool(sh_enabled),
                'self_heal_marketing_cooldown_s': float(sh_cooldown),
                'self_heal_on_sla': bool(sh_on_sla),
                'self_heal_on_qsize': bool(sh_on_qsize),
                'self_heal_on_drops': bool(sh_on_drops),
                'self_heal_purge_enabled': bool(purge_enabled),
                'self_heal_purge_kinds_blacklist': tuple(purge_blacklist),
                'self_heal_purge_kinds_whitelist': tuple(purge_whitelist),
                'self_heal_purge_max_items': int(purge_max_items),
            },
        )

        telegram_outbound_queue.start()
        return telegram_outbound_queue
    except Exception as exc:
        log_exception_throttled(LOGGER, "boot_phase_outbound_build_failed", exc)
        try:
            logging_mod.getLogger("runtime.telegram.outbound").warning(
                "telegram_outbound_queue_disabled err=%s",
                exc.__class__.__name__,
            )
        except Exception as nested_exc:
            log_exception_throttled(LOGGER, "boot_phase_outbound_warning_failed", nested_exc)
        return None


def configure_sla_budget(*, settings: Any) -> None:
    try:
        from runtime.observability.perf import set_sla_budget_ms

        set_sla_budget_ms(int(getattr(settings.perf, "sla_button_budget_ms", 300) or 300))
    except Exception as exc:
        log_exception_throttled(LOGGER, "boot_phase_outbound_sla_budget_failed", exc)
