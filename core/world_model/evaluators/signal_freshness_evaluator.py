from __future__ import annotations

from core.world_model.enums import SignalFreshness
from core.world_model.types import FreshnessReport, ReaderBundle


class SignalFreshnessEvaluator:
    def __init__(self, *, stale_after_ms: int = 6 * 60 * 60 * 1000) -> None:
        self._stale_after_ms = int(stale_after_ms)

    def evaluate(self, *, now_ms: int, readers: ReaderBundle) -> FreshnessReport:
        reader_map = {
            "customer": readers.customer,
            "revenue": readers.revenue,
            "campaign": readers.campaign,
            "product": readers.product,
            "messaging": readers.messaging,
            "market": readers.market,
        }
        per_reader = {}
        age_ms = {}
        worst = SignalFreshness.FRESH
        for name, result in reader_map.items():
            observed = result.observed_at_ms
            age = None if observed is None else max(0, int(now_ms) - int(observed))
            age_ms[name] = age
            if result.payload is None:
                status = SignalFreshness.MISSING
            elif age is not None and age > self._stale_after_ms:
                status = SignalFreshness.STALE
            else:
                status = SignalFreshness.FRESH
            per_reader[name] = status
            if status == SignalFreshness.MISSING:
                worst = SignalFreshness.MISSING
            elif status == SignalFreshness.STALE and worst != SignalFreshness.MISSING:
                worst = SignalFreshness.STALE
        return FreshnessReport(per_reader=per_reader, age_ms=age_ms, worst_status=worst)
