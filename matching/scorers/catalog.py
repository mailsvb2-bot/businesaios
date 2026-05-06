from __future__ import annotations


class CapacityFitScore:
    NAME = "capacity_fit_score"
    WEIGHT = 1.0

    def score(self, *, intent, profile, live_state) -> float:
        return live_state.capacity_score


class ConversionProbabilityScore:
    NAME = "conversion_probability_score"
    WEIGHT = 1.0

    def score(self, *, intent, profile, live_state) -> float:
        return live_state.conversion_score


class CustomerSatisfactionProbabilityScore:
    NAME = "customer_satisfaction_probability_score"
    WEIGHT = 1.0

    def score(self, *, intent, profile, live_state) -> float:
        return live_state.quality_score


class FairDistributionScore:
    NAME = "fair_distribution_score"
    WEIGHT = 1.0

    def score(self, *, intent, profile, live_state) -> float:
        return 0.6 if 'new_supply' in profile.tags else 0.5


class GeoFitScore:
    NAME = "geo_fit_score"
    WEIGHT = 1.0

    def score(self, *, intent, profile, live_state) -> float:
        return 1.0 if (not intent.location_hint or intent.location_hint in profile.service_area_codes or 'remote' in profile.service_area_codes) else 0.2


class IntentFitScore:
    NAME = "intent_fit_score"
    WEIGHT = 1.0

    def score(self, *, intent, profile, live_state) -> float:
        return 1.0 if intent.service_type in profile.service_categories else 0.3


class PriceFitScore:
    NAME = "price_fit_score"
    WEIGHT = 1.0

    def score(self, *, intent, profile, live_state) -> float:
        bands = {'low': 1, 'mid': 2, 'high': 3}
        return max(0.0, 1.0 - abs(bands.get(intent.budget_band, 2) - bands.get(profile.price_band, 2)) * 0.4)


class RepeatPurchaseProbabilityScore:
    NAME = "repeat_purchase_probability_score"
    WEIGHT = 1.0

    def score(self, *, intent, profile, live_state) -> float:
        return 0.8 if intent.is_repeat_customer else 0.5


class ReputationFitScore:
    NAME = "reputation_fit_score"
    WEIGHT = 1.0

    def score(self, *, intent, profile, live_state) -> float:
        return live_state.reputation_score


class ResponseFitScore:
    NAME = "response_fit_score"
    WEIGHT = 1.0

    def score(self, *, intent, profile, live_state) -> float:
        return live_state.response_speed_score


class RevenuePotentialScore:
    NAME = "revenue_potential_score"
    WEIGHT = 1.0

    def score(self, *, intent, profile, live_state) -> float:
        return max(0.0, min(1.0, live_state.margin_score * (1.0 if intent.is_high_value else 0.7)))


class RiskPenaltyScore:
    NAME = "risk_penalty_score"
    WEIGHT = 1.0

    def score(self, *, intent, profile, live_state) -> float:
        return 1.0 - live_state.risk_score


SCORER_COMPAT_EXPORTS = {
    'CapacityFitScore': 'capacity_fit_score',
    'ConversionProbabilityScore': 'conversion_probability_score',
    'CustomerSatisfactionProbabilityScore': 'customer_satisfaction_probability_score',
    'FairDistributionScore': 'fair_distribution_score',
    'GeoFitScore': 'geo_fit_score',
    'IntentFitScore': 'intent_fit_score',
    'PriceFitScore': 'price_fit_score',
    'RepeatPurchaseProbabilityScore': 'repeat_purchase_probability_score',
    'ReputationFitScore': 'reputation_fit_score',
    'ResponseFitScore': 'response_fit_score',
    'RevenuePotentialScore': 'revenue_potential_score',
    'RiskPenaltyScore': 'risk_penalty_score',
}

__all__ = tuple(['SCORER_COMPAT_EXPORTS'] + list(SCORER_COMPAT_EXPORTS))
