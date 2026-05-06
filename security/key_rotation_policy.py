from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


CANON_KEY_ROTATION_POLICY = True


@dataclass(frozen=True)
class KeyRotationVerdict:
    should_rotate: bool
    reason: str


class KeyRotationPolicy:
    def __init__(self, *, max_age_days: int = 90) -> None:
        self._max_age_days = max(int(max_age_days), 1)

    def evaluate(self, *, created_at: datetime, now: datetime | None = None) -> KeyRotationVerdict:
        moment = now or datetime.now(timezone.utc)
        if created_at.tzinfo is None or moment.tzinfo is None:
            raise ValueError('timestamps must be timezone-aware')
        age_days = (moment - created_at).total_seconds() / 86400.0
        if age_days >= self._max_age_days:
            return KeyRotationVerdict(True, f'key age exceeded {self._max_age_days} days')
        return KeyRotationVerdict(False, 'key age within policy')


__all__ = [
    'CANON_KEY_ROTATION_POLICY',
    'KeyRotationPolicy',
    'KeyRotationVerdict',
]
