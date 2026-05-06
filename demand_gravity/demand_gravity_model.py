from __future__ import annotations

from dataclasses import dataclass

from config.demand_scoring import GRAVITY_WEIGHTS
from shared.numbers import coerce_float


@dataclass(frozen=True, slots=True)
class GravityVector:
    business_id: str
    attraction: float
    demand_pressure: float
    supply_pressure: float
    geo_distance_penalty: float


class DemandGravityModel:
    """Approximate demand flow so matching is not blind to market pressure."""

    def _geo_penalty(self, *, intent, profile) -> float:
        location = str(getattr(intent, 'location_hint', '') or '').strip().lower()
        areas = {str(item).strip().lower() for item in getattr(profile, 'service_area_codes', ()) or ()}
        if not location:
            return GRAVITY_WEIGHTS.missing_location_penalty
        return 0.0 if location in areas or 'remote' in areas else GRAVITY_WEIGHTS.geo_mismatch_penalty

    def _demand_pressure(self, *, intent) -> float:
        urgency = str(getattr(intent, 'urgency', '') or '').strip().lower()
        high_value = bool(getattr(intent, 'is_high_value', False))
        trust_required = bool(getattr(intent, 'needs_trust', False))
        pressure = GRAVITY_WEIGHTS.base_demand_pressure
        if urgency in {'high', 'urgent', 'now'}:
            pressure += GRAVITY_WEIGHTS.urgency_bonus
        if high_value:
            pressure += GRAVITY_WEIGHTS.high_value_bonus
        if trust_required:
            pressure += GRAVITY_WEIGHTS.trust_bonus
        return max(0.0, min(1.0, pressure))

    def _supply_pressure(self, *, live_state) -> float:
        queue_load = coerce_float(getattr(live_state, 'queue_load', 0.0), 0.0)
        capacity = coerce_float(getattr(live_state, 'capacity_score', 0.0), 0.0)
        response = coerce_float(getattr(live_state, 'response_speed_score', 0.0), 0.0)
        risk = coerce_float(getattr(live_state, 'risk_score', 0.0), 0.0)
        pressure = (
            GRAVITY_WEIGHTS.base_supply_pressure
            + (queue_load * GRAVITY_WEIGHTS.queue_weight)
            - (capacity * GRAVITY_WEIGHTS.capacity_weight)
            - (response * GRAVITY_WEIGHTS.response_weight)
            + (risk * GRAVITY_WEIGHTS.risk_weight)
        )
        return max(0.0, min(1.0, pressure))

    def vector_for(self, *, intent, profile, live_state) -> GravityVector:
        geo_penalty = self._geo_penalty(intent=intent, profile=profile)
        demand_pressure = self._demand_pressure(intent=intent)
        supply_pressure = self._supply_pressure(live_state=live_state)
        quality = coerce_float(getattr(live_state, 'quality_score', 0.0), 0.0)
        response = coerce_float(getattr(live_state, 'response_speed_score', 0.0), 0.0)
        margin = coerce_float(getattr(live_state, 'margin_score', 0.0), 0.0)
        features = getattr(live_state, 'features', {}) or {}
        if not isinstance(features, dict):
            features = {}
        feature_geo = coerce_float(features.get('geo_fit'), 0.0)
        feature_time = coerce_float(features.get('time_fit'), 0.0)
        attraction = max(
            0.0,
            min(
                1.0,
                (quality * GRAVITY_WEIGHTS.quality_weight)
                + (response * GRAVITY_WEIGHTS.attraction_response_weight)
                + (margin * GRAVITY_WEIGHTS.margin_weight)
                + (feature_geo * GRAVITY_WEIGHTS.feature_geo_weight)
                + (feature_time * GRAVITY_WEIGHTS.feature_time_weight)
                + (demand_pressure * GRAVITY_WEIGHTS.attraction_demand_weight)
                - (supply_pressure * GRAVITY_WEIGHTS.attraction_supply_penalty)
                - geo_penalty,
            ),
        )
        return GravityVector(
            business_id=str(getattr(profile, 'business_id', '')),
            attraction=attraction,
            demand_pressure=demand_pressure,
            supply_pressure=supply_pressure,
            geo_distance_penalty=geo_penalty,
        )
