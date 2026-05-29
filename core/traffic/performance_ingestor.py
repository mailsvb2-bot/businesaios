from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable


@dataclass(frozen=True)
class PerformanceIngestor:
    """Normalize ads metrics points into a compact dict for read-model ingestion.

    IMPORTANT: core must not import connector types. This ingestor accepts
    dict-like points (or objects with the same attributes) to remain provider-agnostic.
    """

    def summarize(self, points: Iterable[Any]) -> dict[str, int]:
        clicks = 0
        impressions = 0
        spend_minor = 0
        conv = 0
        for p in points or []:
            try:
                clicks += int(getattr(p, "clicks", None) or (p.get("clicks") if isinstance(p, dict) else 0) or 0)
                impressions += int(getattr(p, "impressions", None) or (p.get("impressions") if isinstance(p, dict) else 0) or 0)
                spend = getattr(p, "spend", None)
                if spend is None and isinstance(p, dict):
                    spend = p.get("spend")
                spend_minor += int(round(float(spend or 0.0) * 100))
                conversions = getattr(p, "conversions", None)
                if conversions is None and isinstance(p, dict):
                    conversions = p.get("conversions")
                conv += int(conversions or 0)
            except Exception:
                continue
        return {"impressions": impressions, "clicks": clicks, "spend_minor": spend_minor, "conversions": conv}
