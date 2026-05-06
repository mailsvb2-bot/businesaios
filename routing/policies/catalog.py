from __future__ import annotations

from config.demand_scoring import ROUTING_POLICY_DELTAS


class CapacityProtectionPolicy:
    NAME = "CapacityProtectionPolicy"

    def adjust(self, *, intent, profile, live_state) -> float:
        return -ROUTING_POLICY_DELTAS.low_capacity_penalty if live_state.capacity_score <= ROUTING_POLICY_DELTAS.low_capacity_threshold else 0.0


class FairRotationPolicy:
    NAME = "FairRotationPolicy"

    def adjust(self, *, intent, profile, live_state) -> float:
        return ROUTING_POLICY_DELTAS.fair_rotation_bonus if 'new_supply' in profile.tags else 0.0


class FastResponsePolicy:
    NAME = "FastResponsePolicy"

    def adjust(self, *, intent, profile, live_state) -> float:
        return ROUTING_POLICY_DELTAS.fast_response_bonus if live_state.response_speed_score >= ROUTING_POLICY_DELTAS.fast_response_threshold else 0.0


class GeoLocalityPolicy:
    NAME = "GeoLocalityPolicy"

    def adjust(self, *, intent, profile, live_state) -> float:
        return ROUTING_POLICY_DELTAS.geo_local_bonus if (not intent.location_hint or intent.location_hint in profile.service_area_codes) else -ROUTING_POLICY_DELTAS.geo_mismatch_penalty


class HighRiskRequestPolicy:
    NAME = "HighRiskRequestPolicy"

    def adjust(self, *, intent, profile, live_state) -> float:
        return -ROUTING_POLICY_DELTAS.high_risk_penalty if live_state.risk_score > ROUTING_POLICY_DELTAS.high_risk_threshold else 0.0


class HighValueClientPolicy:
    NAME = "HighValueClientPolicy"

    def adjust(self, *, intent, profile, live_state) -> float:
        return ROUTING_POLICY_DELTAS.high_value_premium_bonus if intent.is_high_value and 'premium' in profile.tags else 0.0


class NewBusinessRampPolicy:
    NAME = "NewBusinessRampPolicy"

    def adjust(self, *, intent, profile, live_state) -> float:
        return ROUTING_POLICY_DELTAS.new_business_bonus if 'new_supply' in profile.tags else 0.0


class PremiumSupplyPolicy:
    NAME = "PremiumSupplyPolicy"

    def adjust(self, *, intent, profile, live_state) -> float:
        return ROUTING_POLICY_DELTAS.premium_quality_bonus if intent.quality_band == 'high' and 'premium' in profile.tags else 0.0


class ReputationSafetyPolicy:
    NAME = "ReputationSafetyPolicy"

    def adjust(self, *, intent, profile, live_state) -> float:
        return -ROUTING_POLICY_DELTAS.low_reputation_penalty if live_state.reputation_score < ROUTING_POLICY_DELTAS.low_reputation_threshold else 0.0


def build_default_policies() -> tuple[object, ...]:
    return (
        HighValueClientPolicy(),
        GeoLocalityPolicy(),
        FastResponsePolicy(),
        CapacityProtectionPolicy(),
        PremiumSupplyPolicy(),
        FairRotationPolicy(),
        NewBusinessRampPolicy(),
        ReputationSafetyPolicy(),
        HighRiskRequestPolicy(),
    )


ROUTING_POLICY_COMPAT_EXPORTS = {
    'CapacityProtectionPolicy': 'capacity_protection_policy',
    'FairRotationPolicy': 'fair_rotation_policy',
    'FastResponsePolicy': 'fast_response_policy',
    'GeoLocalityPolicy': 'geo_locality_policy',
    'HighRiskRequestPolicy': 'high_risk_request_policy',
    'HighValueClientPolicy': 'high_value_client_policy',
    'NewBusinessRampPolicy': 'new_business_ramp_policy',
    'PremiumSupplyPolicy': 'premium_supply_policy',
    'ReputationSafetyPolicy': 'reputation_safety_policy',
    'build_default_policies': 'routing_policy_registry',
}

__all__ = tuple(['ROUTING_POLICY_COMPAT_EXPORTS'] + list(ROUTING_POLICY_COMPAT_EXPORTS))
