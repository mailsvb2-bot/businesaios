from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping

CANON_SAFETY_ROLLBACK_VERIFIER = True


class RollbackVerificationError(ValueError):
    pass


@dataclass(frozen=True)
class RollbackVerificationResult:
    verified: bool
    checked_keys: tuple[str, ...]
    drift_keys: tuple[str, ...] = ()


class RollbackVerifier:
    def verify(self, *, expected_state: Mapping[str, Any], observed_state: Mapping[str, Any]) -> RollbackVerificationResult:
        expected = dict(expected_state or {})
        observed = dict(observed_state or {})
        checked_keys: list[str] = []
        drift_keys: list[str] = []
        for key, expected_value in expected.items():
            checked_keys.append(str(key))
            if key not in observed:
                drift_keys.append(str(key))
                raise RollbackVerificationError(f'missing rollback state key: {key}')
            if observed[key] != expected_value:
                drift_keys.append(str(key))
                raise RollbackVerificationError(
                    f'rollback state mismatch for {key}: {observed[key]!r} != {expected_value!r}'
                )
        return RollbackVerificationResult(
            verified=True,
            checked_keys=tuple(checked_keys),
            drift_keys=tuple(drift_keys),
        )


__all__ = ['CANON_SAFETY_ROLLBACK_VERIFIER', 'RollbackVerificationError', 'RollbackVerificationResult', 'RollbackVerifier']
