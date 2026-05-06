from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any, Mapping
import json

CANON_ECONOMIC_BUNDLE_IMMUTABILITY = True


def _safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: object) -> str:
    return str(value or '').strip()


def _stable_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


@dataclass(frozen=True, slots=True)
class EconomicBundleImmutabilityVerdict:
    valid: bool
    immutable: bool
    payload_digest: str
    reason: str = 'economic_bundle_immutable_valid'
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'valid': bool(self.valid),
            'immutable': bool(self.immutable),
            'payload_digest': self.payload_digest,
            'reason': self.reason,
            'metadata': dict(self.metadata),
        }


class EconomicBundleImmutabilityValidator:
    def validate(self, *, bundle: Mapping[str, Any]) -> EconomicBundleImmutabilityVerdict:
        normalized = _safe_dict(bundle)
        payload = _safe_dict(normalized.get('payload')) or normalized
        manifest = _safe_dict(payload.get('export_manifest'))
        immutable_bundle = bool(manifest.get('immutable_bundle', True))
        manifest_for_lock = dict(manifest)
        manifest_for_lock.pop('immutable_payload_digest', None)
        payload_for_lock = dict(payload)
        if manifest:
            payload_for_lock['export_manifest'] = manifest_for_lock
        computed_digest = sha256(_stable_json(payload_for_lock).encode('utf-8')).hexdigest()
        locked_digest = _text(manifest.get('immutable_payload_digest')) or _text(normalized.get('digest'))
        valid = True
        reason = 'economic_bundle_immutable_valid'
        if immutable_bundle and locked_digest and locked_digest != computed_digest:
            valid = False
            reason = 'economic_bundle_immutable_digest_mismatch'
        return EconomicBundleImmutabilityVerdict(
            valid=valid,
            immutable=immutable_bundle,
            payload_digest=locked_digest or computed_digest,
            reason=reason,
            metadata={'owner': 'execution.economic_bundle_immutability'},
        )


__all__ = [
    'CANON_ECONOMIC_BUNDLE_IMMUTABILITY',
    'EconomicBundleImmutabilityVerdict',
    'EconomicBundleImmutabilityValidator',
]
