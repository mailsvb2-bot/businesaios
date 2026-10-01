from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from application.business_discovery.owner_assertion_ingress import (
    OwnerAssertionIngressResult,
    OwnerBusinessAssertion,
    OwnerBusinessAssertionIngress,
)
from contracts.event_store import EventStore, supports_event_store

CANON_BUSINESS_DISCOVERY_LEGACY_ONBOARDING_MIGRATION = True
_LEGACY_SETTINGS_KEY = "autopilot:session"
_MIGRATION_NAMESPACE = "business-discovery-legacy-onboarding@v1"

_OLD_STAGE_ORDER = {
    "diag:what": 0,
    "diag:avg_check": 1,
    "diag:margin": 2,
    "diag:region": 3,
    "diag:has_clients": 4,
    "budget:7d": 5,
    "pick:offer": 6,
    "pick:channel": 7,
    "ads:connect": 8,
    "ready:launch": 9,
    "running": 10,
    "audit:stop_loss": 11,
}


@dataclass(frozen=True)
class LegacyOnboardingField:
    field_key: str
    value: Any


@dataclass(frozen=True)
class LegacyOnboardingMigrationResult:
    migrated: tuple[str, ...]
    assertions: tuple[OwnerAssertionIngressResult, ...]


@dataclass(frozen=True)
class LegacyOnboardingSnapshot:
    settings: Mapping[str, Any]
    observed_at_ms: int


class LegacyOnboardingEventReader:
    """Read the latest durable legacy onboarding setting for one owner.

    The reader is intentionally narrow: it reads only the canonical
    user_setting_set event for autopilot:session within the exact tenant/user
    scope and preserves the source event timestamp so migration replays remain
    deterministic.
    """

    def __init__(self, *, event_store: EventStore) -> None:
        if not supports_event_store(event_store):
            raise ValueError("canonical EventStore is required")
        self._events = event_store

    def read(
        self,
        *,
        tenant_id: str,
        user_id: str,
    ) -> LegacyOnboardingSnapshot | None:
        tenant = str(tenant_id or "").strip()
        user = str(user_id or "").strip()
        if not tenant:
            raise ValueError("tenant_id is required")
        if not user:
            raise ValueError("user_id is required")

        latest: tuple[int, int, object] | None = None
        ordinal = 0
        for raw_event in self._events.iter_events(
            tenant_id=tenant,
            start_ms=0,
            user_id=user,
            event_type="user_setting_set",
        ):
            ordinal += 1
            event = dict(raw_event)
            payload = event.get("payload")
            if not isinstance(payload, Mapping):
                continue
            if str(payload.get("key") or "").strip() != _LEGACY_SETTINGS_KEY:
                continue
            timestamp = event.get("timestamp_ms")
            if isinstance(timestamp, bool) or not isinstance(timestamp, int) or timestamp <= 0:
                raise ValueError("legacy onboarding event timestamp must be a positive integer")
            value = payload.get("value")
            candidate = (int(timestamp), ordinal, value)
            if latest is None or candidate[:2] >= latest[:2]:
                latest = candidate

        if latest is None:
            return None
        observed_at_ms, _, session = latest
        if not isinstance(session, Mapping):
            return None
        return LegacyOnboardingSnapshot(
            settings={_LEGACY_SETTINGS_KEY: dict(session)},
            observed_at_ms=observed_at_ms,
        )


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _stage_at_least(stage: str, minimum: str) -> bool:
    current = _OLD_STAGE_ORDER.get(str(stage or "").strip())
    required = _OLD_STAGE_ORDER.get(minimum)
    return current is not None and required is not None and current >= required


def legacy_onboarding_fields(settings: Mapping[str, Any] | None) -> tuple[LegacyOnboardingField, ...]:
    """Project durable legacy onboarding settings into canonical discovery values.

    This is deliberately a one-way compatibility reader. It owns no storage and
    does not make legacy session state authoritative. Ambiguous default values
    from the old Diagnostics dataclass are ignored unless the persisted stage
    proves that the corresponding question was completed.
    """

    root = _mapping(settings)
    session = _mapping(root.get(_LEGACY_SETTINGS_KEY))
    if not session:
        return ()
    diag = _mapping(session.get("diag"))
    stage = str(session.get("stage") or "").strip()
    out: list[LegacyOnboardingField] = []

    what = diag.get("what")
    if isinstance(what, str) and what.strip():
        out.append(LegacyOnboardingField("offer.summary", what.strip()))

    region = diag.get("region")
    if isinstance(region, str) and region.strip():
        out.append(LegacyOnboardingField("market.region", region.strip()))

    if "avg_check_rub" in diag:
        amount_rub = diag.get("avg_check_rub")
        if isinstance(amount_rub, bool) or not isinstance(amount_rub, int) or amount_rub < 0:
            raise ValueError("legacy avg_check_rub must be a non-negative integer")
        out.append(
            LegacyOnboardingField(
                "economics.average_check",
                {"amount_minor": amount_rub * 100, "currency": "RUB"},
            )
        )
    elif "avg_check_minor" in diag and _stage_at_least(stage, "diag:margin"):
        amount_minor = diag.get("avg_check_minor")
        currency = diag.get("currency")
        if isinstance(amount_minor, bool) or not isinstance(amount_minor, int) or amount_minor < 0:
            raise ValueError("legacy avg_check_minor must be a non-negative integer")
        if not isinstance(currency, str) or not currency.strip():
            raise ValueError("legacy average check currency is required")
        out.append(
            LegacyOnboardingField(
                "economics.average_check",
                {"amount_minor": amount_minor, "currency": currency.strip().upper()},
            )
        )

    if "margin_pct" in diag and (
        "avg_check_rub" in diag or _stage_at_least(stage, "diag:region")
    ):
        margin = diag.get("margin_pct")
        if isinstance(margin, bool) or not isinstance(margin, (int, float)):
            raise ValueError("legacy margin_pct must be numeric")
        out.append(LegacyOnboardingField("economics.margin_pct", margin))

    has_clients = diag.get("has_clients")
    if has_clients not in (None, "", "unknown"):
        if not isinstance(has_clients, str):
            raise ValueError("legacy has_clients must be text")
        normalized_clients = has_clients.strip().lower()
        if normalized_clients not in {"yes", "no", "some"}:
            raise ValueError("legacy has_clients value is unsupported")
        out.append(LegacyOnboardingField("sales.has_clients", normalized_clients))

    if "budget_minor_7d" in diag and _stage_at_least(stage, "pick:offer"):
        budget = diag.get("budget_minor_7d")
        currency = diag.get("budget_currency")
        if isinstance(budget, bool) or not isinstance(budget, int) or budget < 0:
            raise ValueError("legacy budget_minor_7d must be a non-negative integer")
        if not isinstance(currency, str) or not currency.strip():
            raise ValueError("legacy budget currency is required")
        out.append(
            LegacyOnboardingField(
                "acquisition.test_budget_7d",
                {"amount_minor": budget, "currency": currency.strip().upper()},
            )
        )

    seen: set[str] = set()
    for item in out:
        if item.field_key in seen:
            raise ValueError(f"duplicate legacy migration target: {item.field_key}")
        seen.add(item.field_key)
    return tuple(out)


class LegacyOnboardingMigrator:
    """One-way legacy settings -> canonical owner assertion ingress."""

    def __init__(self, *, ingress: OwnerBusinessAssertionIngress) -> None:
        self._ingress = ingress

    def migrate(
        self,
        *,
        settings: Mapping[str, Any] | None,
        tenant_id: str,
        business_id: str,
        actor_id: str,
        observed_at_ms: int,
        recorded_at_ms: int | None = None,
    ) -> LegacyOnboardingMigrationResult:
        migrated: list[str] = []
        assertions: list[OwnerAssertionIngressResult] = []
        for item in legacy_onboarding_fields(settings):
            result = self._ingress.ingest(
                assertion=OwnerBusinessAssertion(
                    tenant_id=tenant_id,
                    business_id=business_id,
                    actor_id=actor_id,
                    field_key=item.field_key,
                    value=item.value,
                    observed_at_ms=int(observed_at_ms),
                    occurred_at_ms=int(observed_at_ms),
                    correlation_id=_MIGRATION_NAMESPACE,
                ),
                idempotency_key=f"{_MIGRATION_NAMESPACE}:{item.field_key}",
                recorded_at_ms=recorded_at_ms,
            )
            migrated.append(item.field_key)
            assertions.append(result)
        return LegacyOnboardingMigrationResult(
            migrated=tuple(migrated),
            assertions=tuple(assertions),
        )


__all__ = [
    "CANON_BUSINESS_DISCOVERY_LEGACY_ONBOARDING_MIGRATION",
    "LegacyOnboardingEventReader",
    "LegacyOnboardingField",
    "LegacyOnboardingMigrationResult",
    "LegacyOnboardingMigrator",
    "LegacyOnboardingSnapshot",
    "legacy_onboarding_fields",
]
