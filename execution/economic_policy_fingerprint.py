from __future__ import annotations

import json
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any
from collections.abc import Mapping

CANON_ECONOMIC_POLICY_FINGERPRINT = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


@dataclass(frozen=True, slots=True)
class EconomicPolicyFingerprint:
    fingerprint: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {'fingerprint': self.fingerprint, 'payload': dict(self.payload)}


class EconomicPolicyFingerprintBuilder:
    def build(self, *, scope_profile: Mapping[str, Any]) -> EconomicPolicyFingerprint:
        normalized = {
            'tenant_tier': _safe_dict(scope_profile).get('tenant_tier'),
            'business_tier': _safe_dict(scope_profile).get('business_tier'),
            'export_profile': _safe_dict(scope_profile).get('export_profile'),
            'retention_class': _safe_dict(scope_profile).get('retention_class'),
        }
        fingerprint = sha256(_stable_json(normalized).encode('utf-8')).hexdigest()
        return EconomicPolicyFingerprint(fingerprint=fingerprint, payload=normalized)


__all__ = [
    'CANON_ECONOMIC_POLICY_FINGERPRINT',
    'EconomicPolicyFingerprint',
    'EconomicPolicyFingerprintBuilder',
]
