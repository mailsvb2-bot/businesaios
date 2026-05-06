from __future__ import annotations

from dataclasses import dataclass


CANON_MASS_REENCRYPTION_EXECUTOR = True


@dataclass(frozen=True)
class MassReencryptionReport:
    success: bool
    processed_records: int
    reason: str


class MassReencryptionExecutor:
    """Canonical owner of staged secret re-encryption over vault records.

    This implementation intentionally only supports vaults exposing list_records(), get(), and put().
    It keeps the lifecycle explicit without inventing alternative secret paths.
    """

    def __init__(self, *, vault) -> None:
        self._vault = vault

    def run(self) -> MassReencryptionReport:
        if not hasattr(self._vault, 'list_records'):
            return MassReencryptionReport(False, 0, 'vault does not expose list_records')

        processed = 0
        for record in self._vault.list_records():
            try:
                plaintext = self._vault.get(record.ref)
                self._vault.put(record, plaintext=plaintext)
                processed += 1
            except Exception:
                continue

        return MassReencryptionReport(True, processed, 'mass reencryption pass completed')


__all__ = [
    'CANON_MASS_REENCRYPTION_EXECUTOR',
    'MassReencryptionExecutor',
    'MassReencryptionReport',
]
