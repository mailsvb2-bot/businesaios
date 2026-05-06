from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from execution.channel_roi_memory import ChannelROISnapshot
from execution.roi_confidence_model import ROIConfidenceAssessment

CANON_ADAPTIVE_ROI_MODEL = True


def _clamp(value: float, *, lower: float = -10.0, upper: float = 10.0) -> float:
    return max(lower, min(upper, float(value)))


@dataclass(frozen=True, slots=True)
class AdaptiveROIProjection:
    baseline_expected_roi: float
    adjusted_expected_roi: float
    historical_bias: float
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_expected_roi": float(self.baseline_expected_roi),
            "adjusted_expected_roi": float(self.adjusted_expected_roi),
            "historical_bias": float(self.historical_bias),
            "confidence": float(self.confidence),
            "metadata": dict(self.metadata),
        }


class AdaptiveROIModel:
    """Read-only ROI adjustment helper."""

    def project(self, *, expected_roi: float, memory: ChannelROISnapshot, confidence: ROIConfidenceAssessment) -> AdaptiveROIProjection:
        historical_bias = 0.0
        if memory.verified_samples > 0:
            historical_bias = (memory.positive_roi_rate - 0.5) * 0.4 + (memory.average_expected_roi - expected_roi) * 0.1
        adjusted = _clamp(float(expected_roi) + historical_bias * confidence.confidence)
        return AdaptiveROIProjection(
            baseline_expected_roi=float(expected_roi),
            adjusted_expected_roi=adjusted,
            historical_bias=historical_bias,
            confidence=float(confidence.confidence),
            metadata={"owner": "execution.adaptive_roi_model", "verified_samples": memory.verified_samples},
        )


__all__ = ["CANON_ADAPTIVE_ROI_MODEL", "AdaptiveROIModel", "AdaptiveROIProjection"]
