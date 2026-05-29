from __future__ import annotations

import time
from datetime import UTC, datetime

from .contracts import AdsRLOptSpec, AdsRLState


def _platform(name: str) -> str:
    return str(name).strip().lower()


def build_state_from_ads_metrics(*, ads_service, tenant_id: str, spec: AdsRLOptSpec) -> AdsRLState:
    now_ms = int(time.time() * 1000)
    dt = datetime.fromtimestamp(now_ms / 1000.0, tz=UTC)
    query = {
        "platform": str(spec.platform),
        "campaign_id": str(spec.campaign_id),
        "window_hours": int(spec.window_hours),
    }
    metrics_result = ads_service.metrics(str(tenant_id), query) or {}
    metrics = (metrics_result.get("metrics") if isinstance(metrics_result, dict) else None) or metrics_result

    def _i(key: str) -> int:
        try:
            return int(metrics.get(key) or 0)
        except Exception:
            return 0

    def _f(key: str) -> float:
        try:
            return float(metrics.get(key) or 0.0)
        except Exception:
            return 0.0

    return AdsRLState(
        tenant_id=str(tenant_id),
        platform=_platform(spec.platform),
        campaign_id=str(spec.campaign_id),
        ts_ms=int(now_ms),
        impressions=_i("impressions"),
        clicks=_i("clicks"),
        leads=_i("leads"),
        purchases=_i("purchases"),
        spend=_f("spend"),
        revenue=_f("revenue"),
        day_of_week=int(dt.weekday()),
        hour_of_day=int(dt.hour),
    )
