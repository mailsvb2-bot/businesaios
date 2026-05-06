from __future__ import annotations

from importlib import import_module
from typing import Any

CANON_ROUTING_POLICY_OWNER_SURFACE = True
CANON_ROUTING_POLICY_COMPAT_SHIM = True
_OWNER_MODULE = 'routing.policies.catalog'
_OWNER_EXPORTS = [
    'CapacityProtectionPolicy', 'FairRotationPolicy', 'FastResponsePolicy', 'GeoLocalityPolicy',
    'HighRiskRequestPolicy', 'HighValueClientPolicy', 'NewBusinessRampPolicy', 'PremiumSupplyPolicy',
    'ReputationSafetyPolicy', 'build_default_policies'
]
_ALIAS_EXPORTS = {
    'capacity_protection_policy': 'CapacityProtectionPolicy',
    'fair_rotation_policy': 'FairRotationPolicy',
    'fast_response_policy': 'FastResponsePolicy',
    'geo_locality_policy': 'GeoLocalityPolicy',
    'high_risk_request_policy': 'HighRiskRequestPolicy',
    'high_value_client_policy': 'HighValueClientPolicy',
    'new_business_ramp_policy': 'NewBusinessRampPolicy',
    'premium_supply_policy': 'PremiumSupplyPolicy',
    'reputation_safety_policy': 'ReputationSafetyPolicy',
    'routing_policy_registry': 'build_default_policies',
}

def _owner() -> Any:
    return import_module(_OWNER_MODULE)

def __getattr__(name: str) -> Any:
    if name in {'CANON_ROUTING_POLICY_OWNER_SURFACE', 'CANON_ROUTING_POLICY_COMPAT_SHIM'}:
        return globals()[name]
    if name in _OWNER_EXPORTS:
        return getattr(_owner(), name)
    raise AttributeError(name)

def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__) | set(_OWNER_EXPORTS))

__all__ = ['CANON_ROUTING_POLICY_COMPAT_SHIM', 'CANON_ROUTING_POLICY_OWNER_SURFACE', *_OWNER_EXPORTS]
