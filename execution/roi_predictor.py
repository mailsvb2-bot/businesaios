from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from execution.adaptive_roi_model import AdaptiveROIProjection
from execution.roi_confidence_model import ROIConfidenceAssessment

CANON_ROI_PREDICTOR = True


@dataclass(frozen=True, slots=True)
class ROIPrediction:
    expected_roi: float
    downside_roi: float
    upside_roi: float
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"expected_roi": float(self.expected_roi), "downside_roi": float(self.downside_roi), "upside_roi": float(self.upside_roi), "confidence": float(self.confidence), "metadata": dict(self.metadata)}


class ROIPredictor:
    def predict(self, *, adaptive_projection: AdaptiveROIProjection, confidence: ROIConfidenceAssessment) -> ROIPrediction:
        spread = max(0.1, 1.0 - confidence.confidence)
        expected_roi = adaptive_projection.adjusted_expected_roi
        return ROIPrediction(
            expected_roi=expected_roi,
            downside_roi=expected_roi - spread,
            upside_roi=expected_roi + spread,
            confidence=confidence.confidence,
            metadata={"owner": "execution.roi_predictor"},
        )


__all__ = ["CANON_ROI_PREDICTOR", "ROIPrediction", "ROIPredictor"]
