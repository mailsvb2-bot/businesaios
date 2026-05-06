from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from hashlib import sha256
from typing import Mapping

from config.demand_thresholds import DEDUP_WINDOW_MINUTES


def _hash(parts: list[str]) -> str:
    joined = '|'.join(part.strip().lower() for part in parts if part)
    return sha256(joined.encode('utf-8')).hexdigest()[:16] if joined else ''


@dataclass(frozen=True)
class DedupDecision:
    is_duplicate: bool
    reason: str
    matched_key: str | None


class RequestDeduplicator:
    def __init__(self, dedup_window_minutes: int = DEDUP_WINDOW_MINUTES) -> None:
        self._window_ms = max(1, int(dedup_window_minutes)) * 60 * 1000
        self._seen: dict[str, int] = {}
        self._order: deque[tuple[str, int]] = deque()

    def _prune(self, created_at_ms: int) -> None:
        horizon = int(created_at_ms) - self._window_ms * 2
        while self._order and self._order[0][1] < horizon:
            key, ts = self._order.popleft()
            if self._seen.get(key) == ts:
                self._seen.pop(key, None)

    def _candidate_keys(self, payload: Mapping[str, object]) -> list[tuple[str, str]]:
        request_id = str(payload.get('request_id', ''))
        phone = str(payload.get('phone', ''))
        email = str(payload.get('email', ''))
        customer_id = str(payload.get('customer_id', ''))
        service = str(payload.get('service_key', payload.get('intent_key', '')))
        out: list[tuple[str, str]] = []
        if request_id:
            out.append((f'request:{request_id}', 'request_id'))
        contact_hash = _hash([phone, email, customer_id, service])
        if contact_hash:
            out.append((f'contact:{contact_hash}', 'contact_fingerprint'))
        return out

    def evaluate(self, payload: Mapping[str, object], created_at_ms: int) -> DedupDecision:
        now = int(created_at_ms)
        self._prune(now)
        keys = self._candidate_keys(payload)
        for key, reason in keys:
            prev = self._seen.get(key)
            if prev is not None and abs(now - prev) <= self._window_ms:
                for refresh_key, _ in keys:
                    self._seen[refresh_key] = now
                    self._order.append((refresh_key, now))
                return DedupDecision(True, reason, key)
        for key, _ in keys:
            self._seen[key] = now
            self._order.append((key, now))
        return DedupDecision(False, 'new_request', None)

    def is_duplicate(self, request_id: str, created_at_ms: int) -> bool:
        return self.evaluate({'request_id': request_id}, int(created_at_ms)).is_duplicate
