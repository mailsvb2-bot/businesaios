from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TenantProfile:
    tenant_id: str
    timezone: str = "UTC"  # e.g. "Europe/Amsterdam"
    currency: str = "RUB"
    report_hour_local: int = 10
    report_minute_local: int = 0

    @staticmethod
    def key(tenant_id: str) -> str:
        return f"tenant_profile:{tenant_id}"
