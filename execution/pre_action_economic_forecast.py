from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from execution.adaptive_roi_model import AdaptiveROIModel
from execution.channel_roi_memory import ChannelROISnapshot
from execution.economic_simulator import EconomicSimulator
from execution.roi_confidence_model import ROIConfidenceModel
from execution.roi_predictor import ROIPredictor
from execution.survival_hysteresis import SurvivalHysteresis

CANON_PRE_ACTION_ECONOMIC_FORECAST = True


@dataclass(frozen=True, slots=True)
class PreActionEconomicForecast:
    confidence: dict[str, Any]
    adaptive_projection: dict[str, Any]
    prediction: dict[str, Any]
    simulation: dict[str, Any]
    survival_transition: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "confidence": dict(self.confidence),
            "adaptive_projection": dict(self.adaptive_projection),
            "prediction": dict(self.prediction),
            "simulation": dict(self.simulation),
            "survival_transition": dict(self.survival_transition),
            "metadata": dict(self.metadata),
        }


class PreActionEconomicForecastBuilder:
    def __init__(self) -> None:
        self._confidence_model = ROIConfidenceModel()
        self._adaptive_roi_model = AdaptiveROIModel()
        self._predictor = ROIPredictor()
        self._simulator = EconomicSimulator()
        self._hysteresis = SurvivalHysteresis()

    def build(self, *, expected_roi: float, requested_budget: float, current_survival_mode: str, runway_days_after_action: float, memory: ChannelROISnapshot) -> PreActionEconomicForecast:
        confidence = self._confidence_model.assess(memory=memory, expected_roi=expected_roi)
        adaptive_projection = self._adaptive_roi_model.project(expected_roi=expected_roi, memory=memory, confidence=confidence)
        prediction = self._predictor.predict(adaptive_projection=adaptive_projection, confidence=confidence)
        simulation = self._simulator.simulate(requested_budget=requested_budget, prediction=prediction)
        survival_transition = self._hysteresis.recommend(current_mode=current_survival_mode, confidence=confidence.confidence, runway_days_after_action=runway_days_after_action)
        return PreActionEconomicForecast(
            confidence=confidence.to_dict(),
            adaptive_projection=adaptive_projection.to_dict(),
            prediction=prediction.to_dict(),
            simulation=simulation.to_dict(),
            survival_transition=survival_transition.to_dict(),
            metadata={"owner": "execution.pre_action_economic_forecast"},
        )


__all__ = ["CANON_PRE_ACTION_ECONOMIC_FORECAST", "PreActionEconomicForecast", "PreActionEconomicForecastBuilder"]
