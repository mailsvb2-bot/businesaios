from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


CANON_EMERGENCY_SECURITY_REVOKE = True


@dataclass(frozen=True)
class EmergencyRevokeReport:
    success: bool
    revoked_key_ids: tuple[str, ...]
    revoked_token_fingerprints: tuple[str, ...]
    incident_id: int
    reason: str


class EmergencySecurityRevoke:
    """Canonical owner of emergency revoke/quarantine actions."""

    def __init__(self, *, key_provider, token_revocation_store, incident_registry) -> None:
        self._keys = key_provider
        self._tokens = token_revocation_store
        self._incidents = incident_registry

    def execute(
        self,
        *,
        reason: str,
        key_ids: Sequence[str] = (),
        token_fingerprints: Sequence[str] = (),
    ) -> EmergencyRevokeReport:
        incident_id = self._incidents.open_incident(
            incident_kind='security.emergency_revoke',
            payload={
                'reason': str(reason),
                'key_ids': list(key_ids),
                'token_fingerprints': list(token_fingerprints),
            },
        )

        revoked_keys: list[str] = []
        for key_id in key_ids:
            try:
                self._keys.revoke(str(key_id))
                revoked_keys.append(str(key_id))
            except Exception:
                continue

        revoked_tokens: list[str] = []
        for fingerprint in token_fingerprints:
            self._tokens.revoke(token_fingerprint=str(fingerprint), reason=str(reason))
            revoked_tokens.append(str(fingerprint))

        return EmergencyRevokeReport(
            success=True,
            revoked_key_ids=tuple(revoked_keys),
            revoked_token_fingerprints=tuple(revoked_tokens),
            incident_id=incident_id,
            reason='emergency revoke executed',
        )


__all__ = [
    'CANON_EMERGENCY_SECURITY_REVOKE',
    'EmergencyRevokeReport',
    'EmergencySecurityRevoke',
]
