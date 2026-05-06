from __future__ import annotations

from dataclasses import dataclass

from security.key_management_contract import KeyPurpose


CANON_REENCRYPTION_ORCHESTRATOR = True


@dataclass(frozen=True)
class ReencryptionReport:
    success: bool
    old_key_id: str
    new_key_id: str
    reason: str


class ReencryptionOrchestrator:
    """Stages key rotation using existing provider semantics.

    Real data rewrap remains owned by storage/vault layers. This owner keeps the
    rotation lifecycle explicit without inventing a second truth.
    """

    def __init__(self, *, key_provider, rotation_journal) -> None:
        self._key_provider = key_provider
        self._journal = rotation_journal

    def rotate_secret_encryption_key(self, *, current_key_id: str, new_key_id: str) -> ReencryptionReport:
        current = self._key_provider.get(current_key_id)
        rotated = self._key_provider.rotate(current_key_id=current_key_id, new_key_id=new_key_id)
        self._journal.append(
            key_id=current_key_id,
            old_status=current.status.value,
            new_status='deprecated',
            payload={
                'new_key_id': rotated.key_id,
                'purpose': current.purpose.value,
            },
        )
        return ReencryptionReport(
            success=True,
            old_key_id=current_key_id,
            new_key_id=rotated.key_id,
            reason='rotation created new active key',
        )


__all__ = [
    'CANON_REENCRYPTION_ORCHESTRATOR',
    'ReencryptionOrchestrator',
    'ReencryptionReport',
]
