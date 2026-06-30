"""Telegram polling via DecisionCore + RuntimeExecutor.

Contract: _decide MUST be DecisionCore.decide (single decision source).
No SDK or network imports live here.
"""

from __future__ import annotations


import logging
import time
from dataclasses import dataclass
from typing import Any

from core.observability.silent import swallow
from interfaces.telegram.runtime.telegram_runtime_worldstate_builder import build_system_world_state
from runtime.platform.config.env_flags import env_str

log = logging.getLogger(__name__)


@dataclass
class PollerConfig:
    poll_timeout_s: int = 30
    poll_limit: int = 50


class TelegramPoller:
    def __init__(self, *, decide_fn: Any, execute_fn: Any, cfg: PollerConfig):
        self._decide = decide_fn
        self._execute = execute_fn
        self._cfg = cfg
        self._offset: int | None = None

    @property
    def offset(self) -> int | None:
        return self._offset

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)

    def poll(self) -> list[dict[str, Any]]:
        ws = build_system_world_state(
            source="ingress_poll",
            session={
                "offset": self._offset,
                "timeout_s": int(self._cfg.poll_timeout_s),
                "limit": int(self._cfg.poll_limit),
            },
            user_timezone=env_str("SYSTEM_TZ", "Europe/Amsterdam"),
            now_ms=self._now_ms(),
        )
        env = self._decide(ws)
        res = self._execute(env)
        if not getattr(res, "ok", True):
            return []
        out = getattr(res, "output", None)
        if not isinstance(out, dict):
            return []

        meta = out.get("meta") or {}
        mode = meta.get("mode") if isinstance(meta, dict) else None
        reason = meta.get("reason") if isinstance(meta, dict) else None
        if mode is None:
            mode = out.get("mode")
        if reason is None:
            reason = out.get("reason")
        if mode == "stub" and isinstance(reason, str):
            raise SystemExit(f"Telegram transport is in stub mode: {reason}")
        if out.get("ok") is False:
            err = out.get("error") or reason or "telegram poll failed"
            raise RuntimeError(str(err))

        updates = out.get("updates") or []
        if not isinstance(updates, list):
            updates = []

        try:
            max_upd = max(int(u.get("update_id")) for u in updates if isinstance(u, dict) and u.get("update_id") is not None)
            self._offset = int(max_upd) + 1
        except Exception:
            swallow(__name__, "interfaces/telegram/pipeline/poller.py")
        return updates
