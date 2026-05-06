from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from execution.channel_roi_memory import ChannelROISnapshot

CANON_ROI_CONFIDENCE_MODEL = True


def _clamp(value: float, *, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, float(value)))


@dataclass(frozen=True, slots=True)
class ROIConfidenceAssessment:
    confidence: float
    sample_weight: float
    evidence_weight: float
    stability_weight: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence": float(self.confidence),
            "sample_weight": float(self.sample_weight),
            "evidence_weight": float(self.evidence_weight),
            "stability_weight": float(self.stability_weight),
            "metadata": dict(self.metadata),
        }


class ROIConfidenceModel:
    def assess(self, *, memory: ChannelROISnapshot, expected_roi: float, verified_hint: bool = True) -> ROIConfidenceAssessment:
        sample_weight = _clamp(memory.verified_samples / 5.0)
        evidence_weight = _clamp(memory.positive_roi_rate if memory.verified_samples > 0 else (1.0 if verified_hint else 0.25))
        drift = abs(float(expected_roi) - float(memory.average_expected_roi))
        stability_weight = _clamp(1.0 - min(1.0, drift))
        confidence = _clamp(sample_weight * 0.45 + evidence_weight * 0.35 + stability_weight * 0.20)
        return ROIConfidenceAssessment(
            confidence=confidence,
            sample_weight=sample_weight,
            evidence_weight=evidence_weight,
            stability_weight=stability_weight,
            metadata={"owner": "execution.roi_confidence_model"},
        )


__all__ = ["CANON_ROI_CONFIDENCE_MODEL", "ROIConfidenceAssessment", "ROIConfidenceModel"]
