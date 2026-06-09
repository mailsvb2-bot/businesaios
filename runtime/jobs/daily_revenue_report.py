from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from interfaces.telegram.views.revenue_report_view import render_revenue_report
from runtime.revenue import RevenueReporter, RevenueSprintState, TenantProfile


class KVStore(Protocol):
    def get_json(self, key: str, default: dict) -> dict: ...
    def set_json(self, key: str, value: dict) -> None: ...


class TelegramSender(Protocol):
    async def send_text(self, *, tenant_id: str, text: str) -> None: ...


@dataclass
class DailyRevenueReportJob:
    kv: KVStore
    reporter: RevenueReporter
    tg: TelegramSender

    async def run(self, *, tenant_id: str) -> None:
        now = datetime.now(UTC)

        raw = self.kv.get_json(f"revenue_sprint:{tenant_id}", default={})
        state = RevenueSprintState(**raw) if raw else RevenueSprintState()
        if not state.is_active(now_utc=now):
            return

        prof_raw = self.kv.get_json(TenantProfile.key(tenant_id), default={})
        profile = TenantProfile(**prof_raw) if prof_raw else TenantProfile(tenant_id=tenant_id)
        if not _is_send_time(now_utc=now, tz_name=profile.timezone, hour=profile.report_hour_local, minute=profile.report_minute_local):
            return

        report = self.reporter.build_daily_report(tenant_id=tenant_id, now_utc=now)
        await self.tg.send_text(tenant_id=tenant_id, text=render_revenue_report(report))

        state.day_index = min(state.day_index + 1, 6)
        self.kv.set_json(f"revenue_sprint:{tenant_id}", state.__dict__)


def _is_send_time(*, now_utc: datetime, tz_name: str, hour: int, minute: int) -> bool:
    try:
        from zoneinfo import ZoneInfo
        local = now_utc.astimezone(ZoneInfo(str(tz_name)))
    except Exception:
        local = now_utc
    return (local.hour == int(hour) and local.minute == int(minute))
