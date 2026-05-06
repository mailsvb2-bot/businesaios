from __future__ import annotations

from ml.scoring.base_score_model import BaseScoreModel
from shared.numbers import coerce_float


class AudienceScoreModel(BaseScoreModel):
    def __init__(self) -> None:
        super().__init__(model_name="audience_score_model", feature_weights={"intent_score": 0.4, "match_score": 0.6})


class ChannelScoreModel(BaseScoreModel):
    def __init__(self) -> None:
        super().__init__(model_name="channel_score_model", feature_weights={"historical_roi": 0.7, "volume_fit": 0.3})


class CreativeScoreModel(BaseScoreModel):
    def __init__(self) -> None:
        super().__init__(model_name="creative_score_model", feature_weights={"ctr": 0.2, "conversion_rate": 0.8})


class LeadQualityModel(BaseScoreModel):
    def __init__(self) -> None:
        super().__init__(model_name="lead_quality_model", feature_weights={"intent_score": 0.5, "qualification_score": 0.5})


class PlatformMatchModel(BaseScoreModel):
    def __init__(self) -> None:
        super().__init__(model_name="platform_match_model", feature_weights={"platform_fit": 0.6, "response_speed": 0.4})


class RevenuePotentialModel(BaseScoreModel):
    def __init__(self) -> None:
        super().__init__(model_name="revenue_potential_model", default_base=0.0, default_confidence=0.7, feature_weights={"expected_value": 1.0, "intent_score": 0.5})

    def _score(self, features: dict) -> tuple[float, list[str]]:
        score, reasons = super()._score(features)
        return score, [*reasons, "expected_value_priority"]


class RiskScoreModel(BaseScoreModel):
    def __init__(self) -> None:
        super().__init__(model_name="risk_score_model", default_base=0.0, default_confidence=0.8)

    def _score(self, features: dict) -> tuple[float, list[str]]:
        volatility = coerce_float(features.get("volatility"), 0.0, minimum=0.0)
        risk_flags = coerce_float(features.get("risk_flags"), 0.0, minimum=0.0)
        budget_jump = coerce_float(features.get("budget_delta"), 0.0, minimum=0.0)
        raw = min(1.0, (volatility * 0.4) + (risk_flags * 0.2) + (budget_jump * 1.5))
        return raw, [f"volatility={volatility}", f"risk_flags={risk_flags}", f"budget_jump={budget_jump}"]


class SeoOpportunityModel(BaseScoreModel):
    def __init__(self) -> None:
        super().__init__(model_name="seo_opportunity_model", feature_weights={"search_demand": 0.5, "ranking_gap": 0.5})


__all__ = [
    "AudienceScoreModel",
    "ChannelScoreModel",
    "CreativeScoreModel",
    "LeadQualityModel",
    "PlatformMatchModel",
    "RevenuePotentialModel",
    "RiskScoreModel",
    "SeoOpportunityModel",
]
