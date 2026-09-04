from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

CANON_PROVIDER_PACING = True


class ProviderPacingCas(Protocol):
    def create_if_absent(
        self,
        *,
        key: str,
        payload: Mapping[str, Any],
        ttl_seconds: int | None = None,
    ) -> bool: ...

    def read(self, *, key: str) -> Mapping[str, Any] | None: ...

    def compare_and_swap(
        self,
        *,
        key: str,
        expected_version: int,
        payload: Mapping[str, Any],
        ttl_seconds: int | None = None,
    ) -> bool: ...


@dataclass(frozen=True)
class ProviderPacingRule:
    provider_key: str
    connection_spacing_ms: int
    recipient_spacing_ms: int


@dataclass(frozen=True)
class ProviderPacingReservation:
    provider_key: str
    scheduled_at: datetime
    delay_ms: int
    scope_key: str


_RULES = {
    "max_messaging": ProviderPacingRule(
        provider_key="max_messaging",
        connection_spacing_ms=40,
        recipient_spacing_ms=550,
    ),
}


def _normalize_now(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("provider pacing time must be timezone-aware")
    return value.astimezone(UTC)


def _digest(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _epoch_ms(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def _from_epoch_ms(value: int) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000.0, tz=UTC)


@dataclass(frozen=True)
class ProviderPacingCoordinator:
    cas: ProviderPacingCas
    ttl_seconds: int = 86_400
    max_cas_attempts: int = 32

    def reserve(
        self,
        *,
        tenant_id: str,
        business_id: str,
        provider_key: str,
        recipient_id: str,
        reservation_id: str,
        now: datetime | None = None,
    ) -> ProviderPacingReservation | None:
        rule = _RULES.get(str(provider_key).strip())
        if rule is None:
            return None
        tenant = str(tenant_id).strip()
        business = str(business_id).strip()
        recipient = str(recipient_id).strip()
        reservation = str(reservation_id).strip()
        if not tenant or not business or not recipient or not reservation:
            raise ValueError("provider pacing requires tenant, business, and recipient")
        moment = _normalize_now(now)
        now_ms = _epoch_ms(moment)
        scope_key = _digest(f"{tenant}:{business}:{rule.provider_key}")
        recipient_key = _digest(recipient)
        reservation_key = _digest(reservation)
        for _ in range(max(1, int(self.max_cas_attempts))):
            current = self.cas.read(key=scope_key)
            current_version = 0 if current is None else int(current.get("version") or 0)
            connection_next = 0 if current is None else int(current.get("connection_next_ms") or 0)
            reservation_slots = {
                str(key): int(value)
                for key, value in dict((current or {}).get("reservation_scheduled_ms") or {}).items()
                if int(value) > now_ms - int(self.ttl_seconds) * 1000
            }
            if reservation_key in reservation_slots:
                scheduled_ms = int(reservation_slots[reservation_key])
                return ProviderPacingReservation(
                    provider_key=rule.provider_key,
                    scheduled_at=_from_epoch_ms(scheduled_ms),
                    delay_ms=max(0, scheduled_ms - now_ms),
                    scope_key=scope_key,
                )
            recipient_slots = {
                str(key): int(value)
                for key, value in dict((current or {}).get("recipient_next_ms") or {}).items()
                if int(value) > now_ms - 60_000
            }
            recipient_next = int(recipient_slots.get(recipient_key) or 0)
            scheduled_ms = max(now_ms, connection_next, recipient_next)
            recipient_slots[recipient_key] = scheduled_ms + int(rule.recipient_spacing_ms)
            reservation_slots[reservation_key] = scheduled_ms
            payload = {
                "provider_key": rule.provider_key,
                "connection_next_ms": scheduled_ms + int(rule.connection_spacing_ms),
                "recipient_next_ms": recipient_slots,
                "reservation_scheduled_ms": reservation_slots,
            }
            if current is None:
                committed = self.cas.create_if_absent(
                    key=scope_key,
                    payload=payload,
                    ttl_seconds=self.ttl_seconds,
                )
            else:
                committed = self.cas.compare_and_swap(
                    key=scope_key,
                    expected_version=current_version,
                    payload=payload,
                    ttl_seconds=self.ttl_seconds,
                )
            if committed:
                return ProviderPacingReservation(
                    provider_key=rule.provider_key,
                    scheduled_at=_from_epoch_ms(scheduled_ms),
                    delay_ms=max(0, scheduled_ms - now_ms),
                    scope_key=scope_key,
                )
        raise RuntimeError("provider pacing reservation conflict")


__all__ = [
    "CANON_PROVIDER_PACING",
    "ProviderPacingCoordinator",
    "ProviderPacingReservation",
    "ProviderPacingRule",
]
