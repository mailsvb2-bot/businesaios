from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from core.contracts.revenue_sprint import RevenueSprintConfig, RevenueSprintState


class KVStore(Protocol):
    def get_json(self, key: str, default: dict) -> dict: ...
    def set_json(self, key: str, value: dict) -> None: ...


@dataclass
class BoostResult:
    started: bool
    message: str


class BoostController:
    def __init__(self, *, kv: KVStore, config: RevenueSprintConfig):
        self._kv = kv
        self._cfg = config

    def start_or_status(self, *, tenant_id: str, now_utc: datetime | None = None) -> BoostResult:
        now_utc = (now_utc or datetime.now(UTC)).astimezone(UTC)
        key = f"revenue_sprint:{tenant_id}"
        raw = self._kv.get_json(key, default={})
        state = RevenueSprintState(**raw) if raw else RevenueSprintState()

        if state.is_active(now_utc=now_utc):
            return BoostResult(
                started=False,
                message=f"🚀 Revenue Sprint уже активен. День {state.day_index+1}/{self._cfg.days}.",
            )

        state.start(now_utc=now_utc, days=self._cfg.days)
        self._kv.set_json(key, state.__dict__)

        return BoostResult(
            started=True,
            message=(
                "🚀 Revenue Sprint запущен на 7 дней.\n"
                "Сегодня: включил базовую телеметрию и Autopilot.\n"
                "Завтра утром пришлю первый Revenue Report."
            ),
        )
