from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from collections.abc import Mapping

CANON_BUSINESS_ROI_REGISTRY = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


@dataclass(frozen=True, slots=True)
class BusinessROISignal:
    business_key: str
    adjusted_roi: float
    confidence: float
    revenue_hint: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"business_key": self.business_key, "adjusted_roi": float(self.adjusted_roi), "confidence": float(self.confidence), "revenue_hint": float(self.revenue_hint), "metadata": dict(self.metadata)}


class BusinessROIRegistry:
    def normalize(self, *, entries: Mapping[str, Mapping[str, Any]] | None) -> tuple[BusinessROISignal, ...]:
        payload = _safe_dict(entries)
        rows: list[BusinessROISignal] = []
        for key, raw in payload.items():
            row = _safe_dict(raw)
            rows.append(BusinessROISignal(
                business_key=str(key),
                adjusted_roi=_safe_float(row.get("adjusted_roi") or row.get("expected_roi")),
                confidence=_safe_float(row.get("confidence"), default=0.0),
                revenue_hint=_safe_float(row.get("revenue_hint") or row.get("realized_revenue")),
                metadata={"owner": "execution.business_roi_registry"},
            ))
        return tuple(rows)


__all__ = ["CANON_BUSINESS_ROI_REGISTRY", "BusinessROISignal", "BusinessROIRegistry"]
