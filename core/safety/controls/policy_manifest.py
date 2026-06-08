from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from collections.abc import Mapping

from config.config_versioning import ConfigVersion

from .key_registry import SafetyKeyRegistry

CANON_SAFETY_POLICY_MANIFESTS = True
_POLICY_MANIFEST_SCHEMA_VERSION = 2


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class PolicyManifest:
    tenant_id: str
    policy_scope: str
    policy_payload: Mapping[str, Any]
    fingerprint: str
    signature: str
    issued_at: str = field(default_factory=lambda: _utc_now().isoformat())
    version_id: str = ''
    source: str = 'tenant_config'
    key_id: str = ''
    algorithm: str = 'hmac-sha256'
    schema_version: int = _POLICY_MANIFEST_SCHEMA_VERSION


class PolicyManifestSigner:
    def __init__(self, *, key_registry: SafetyKeyRegistry | None = None) -> None:
        self._keys = key_registry or SafetyKeyRegistry()

    @property
    def current_key_id(self) -> str:
        return self._keys.current.key_id

    @property
    def using_insecure_fallback(self) -> bool:
        return self._keys.current.insecure_fallback

    def build(
        self,
        *,
        tenant_id: str,
        policy_scope: str,
        policy_payload: Mapping[str, Any],
        version: ConfigVersion | None = None,
        source: str = 'tenant_config',
    ) -> PolicyManifest:
        normalized = _normalize(policy_payload)
        fingerprint = _fingerprint(normalized)
        version_id = '' if version is None else str(version.version_id)
        issued_at = _utc_now().isoformat()
        signature = self.sign(
            tenant_id=tenant_id,
            policy_scope=policy_scope,
            fingerprint=fingerprint,
            version_id=version_id,
            source=source,
            issued_at=issued_at,
        )
        return PolicyManifest(
            tenant_id=str(tenant_id),
            policy_scope=str(policy_scope),
            policy_payload=normalized,
            fingerprint=fingerprint,
            signature=signature,
            version_id=version_id,
            source=str(source),
            key_id=self.current_key_id,
            issued_at=issued_at,
        )

    def sign(self, *, tenant_id: str, policy_scope: str, fingerprint: str, version_id: str, source: str, issued_at: str) -> str:
        material = self.signature_material(
            tenant_id=tenant_id,
            policy_scope=policy_scope,
            fingerprint=fingerprint,
            version_id=version_id,
            source=source,
            issued_at=issued_at,
        )
        return hmac.new(self._keys.current.secret, material, hashlib.sha256).hexdigest()

    def signature_material(self, *, tenant_id: str, policy_scope: str, fingerprint: str, version_id: str, source: str, issued_at: str) -> bytes:
        return json.dumps(
            {
                'tenant_id': str(tenant_id),
                'policy_scope': str(policy_scope),
                'fingerprint': str(fingerprint),
                'version_id': str(version_id),
                'source': str(source),
                'issued_at': str(issued_at),
                'schema_version': _POLICY_MANIFEST_SCHEMA_VERSION,
            },
            sort_keys=True,
            separators=(',', ':'),
        ).encode('utf-8')

    def verify(self, manifest: PolicyManifest) -> bool:
        material = self.signature_material(
            tenant_id=manifest.tenant_id,
            policy_scope=manifest.policy_scope,
            fingerprint=manifest.fingerprint,
            version_id=manifest.version_id,
            source=manifest.source,
            issued_at=manifest.issued_at,
        )
        return self._keys.verify_secret(
            str(manifest.key_id or self.current_key_id),
            material,
            str(manifest.signature),
            digestmod=hashlib.sha256,
        )


def _normalize(payload: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(dict(payload or {}), sort_keys=True, default=str))


def _fingerprint(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(dict(payload or {}), sort_keys=True, separators=(',', ':')).encode('utf-8')
    ).hexdigest()


__all__ = ['CANON_SAFETY_POLICY_MANIFESTS', 'PolicyManifest', 'PolicyManifestSigner']
