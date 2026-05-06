from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class CrmRateLimitWindow:
    retry_after_seconds: float = 0.0


class CrmRateLimitPolicy:
    def validate(self, *, requests_per_minute: int, max_allowed: int = 120) -> None:
        if requests_per_minute > max_allowed:
            raise RuntimeError('CRM provider rate limit budget exceeded')

    def parse_window(self, headers: Mapping[str, str]) -> CrmRateLimitWindow:
        raw = headers.get('Retry-After') or headers.get('retry-after') or '0'
        try:
            return CrmRateLimitWindow(retry_after_seconds=max(float(raw), 0.0))
        except (TypeError, ValueError):
            return CrmRateLimitWindow(retry_after_seconds=0.0)
