from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

from application.business_constraint import BusinessConstraintRegistry
from application.business_discovery.contracts import DISCOVERY_FIELDS, DiscoveryFieldSpec
from application.business_discovery.ingress import (
    OwnerAssertionIngressResult,
    OwnerBusinessAssertion,
    OwnerBusinessAssertionIngress,
    ProviderBusinessObservationIngress,
    ProviderObservationIngressResult,
)
from application.business_goal import BusinessGoalRegistry
from contracts.event_store import EventStore, supports_event_store
from runtime.state import StateSynthesisEngine
from runtime.state.state_contract import StateFieldRecord, StateSynthesizedSnapshot

CANON_BUSINESS_DISCOVERY_WORKSPACE = True
_NON_COVERING_VALUE_KINDS = frozenset({"absent", "stale"})


@dataclass(frozen=True)
class BusinessDiscoveryProgress:
    total_fields: int
    covered_fields: int
    owner_asserted_fields: int
    remaining_fields: int
    complete: bool
    next_field_key: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_fields": self.total_fields,
            "covered_fields": self.covered_fields,
            "owner_asserted_fields": self.owner_asserted_fields,
            "remaining_fields": self.remaining_fields,
            "complete": self.complete,
            "next_field_key": self.next_field_key,
        }


class BusinessDiscoveryWorkspace:
    """Authenticated workspace projection over canonical discovery owners.

    This class does not own persistence. Writes delegate to
    OwnerBusinessAssertionIngress; reads come from the canonical state snapshot
    store already owned by runtime.state.
    """

    def __init__(
        self,
        *,
        ingress: OwnerBusinessAssertionIngress,
        state_engine: StateSynthesisEngine,
        goal_registry: BusinessGoalRegistry | None = None,
        constraint_registry: BusinessConstraintRegistry | None = None,
        provider_observation_ingress: ProviderBusinessObservationIngress | None = None,
        legacy_onboarding_reader: LegacyOnboardingEventReader | None = None,
        legacy_onboarding_migrator: LegacyOnboardingMigrator | None = None,
    ) -> None:
        if state_engine.snapshot_store is None:
            raise ValueError("canonical durable StateSnapshotStore is required")
        self._ingress = ingress
        self._state = state_engine
        self._goals = goal_registry
        self._constraints = constraint_registry
        self._provider_observations = provider_observation_ingress
        if (legacy_onboarding_reader is None) != (legacy_onboarding_migrator is None):
            raise ValueError("legacy onboarding reader and migrator must be configured together")
        self._legacy_onboarding_reader = legacy_onboarding_reader
        self._legacy_onboarding_migrator = legacy_onboarding_migrator

    def describe(
        self,
        *,
        tenant_id: str,
        business_id: str,
        actor_id: str | None = None,
    ) -> dict[str, Any]:
        tenant = _required(tenant_id, "tenant_id")
        business = _required(business_id, "business_id")
        actor = str(actor_id or "").strip()
        if actor:
            self._migrate_legacy_onboarding(
                tenant_id=tenant,
                business_id=business,
                actor_id=actor,
            )
        snapshot = self._state.snapshot_store.load_latest(
            tenant_id=tenant,
            business_id=business,
        )
        fields = tuple(
            self._field_view(spec=spec, snapshot=snapshot)
            for spec in DISCOVERY_FIELDS.values()
        )
        progress = _progress(fields)
        return {
            "tenant_id": tenant,
            "business_id": business,
            "state_id": None if snapshot is None else snapshot.state_id,
            "schema_version": "business_discovery_workspace@v1",
            "fields": list(fields),
            "progress": progress.to_dict(),
        }

    def assert_owner(
        self,
        *,
        assertion: OwnerBusinessAssertion,
        idempotency_key: str,
        recorded_at_ms: int | None = None,
    ) -> dict[str, Any]:
        result = self._ingress.ingest(
            assertion=assertion,
            idempotency_key=idempotency_key,
            recorded_at_ms=recorded_at_ms,
        )
        view = self.describe(
            tenant_id=assertion.tenant_id,
            business_id=assertion.business_id,
            actor_id=assertion.actor_id,
        )
        view["assertion"] = _result_payload(result)
        return view

    def reconcile_provider_evidence(
        self,
        *,
        tenant_id: str,
        business_id: str,
        evidence_id: str,
    ) -> dict[str, Any]:
        if self._provider_observations is None:
            raise RuntimeError("canonical provider observation ingress is not configured")
        result = self._provider_observations.reconcile(
            tenant_id=_required(tenant_id, "tenant_id"),
            business_id=_required(business_id, "business_id"),
            evidence_id=_required(evidence_id, "evidence_id"),
        )
        view = self.describe(tenant_id=tenant_id, business_id=business_id)
        view["provider_reconciliation"] = _provider_result_payload(result)
        return view

    def list_goals(self, *, tenant_id: str, business_id: str) -> list[dict[str, Any]]:
        if self._goals is None:
            raise RuntimeError("canonical BusinessGoalRegistry is not configured")
        return [
            _jsonable_dataclass(item)
            for item in self._goals.list_for_business(
                tenant_id=_required(tenant_id, "tenant_id"),
                business_id=_required(business_id, "business_id"),
            )
        ]

    def create_goal(
        self,
        *,
        tenant_id: str,
        business_id: str,
        actor_id: str,
        idempotency_key: str,
        confirmed: bool,
        goal_id: str,
        goal_kind: str,
        target_key: str | None = None,
        metric: str | None = None,
        baseline: float | None = None,
        target: float | None = None,
        deadline_at_ms: int | None = None,
        constraint_ids: tuple[str, ...] = (),
        parent_goal_id: str | None = None,
        priority: int = 50,
        occurred_at_ms: int | None = None,
    ) -> dict[str, Any]:
        if confirmed is not True:
            raise ValueError("explicit owner confirmation is required for canonical goal creation")
        if self._goals is None:
            raise RuntimeError("canonical BusinessGoalRegistry is not configured")
        actor = _required(actor_id, "actor_id")
        goal = self._goals.create(
            tenant_id=_required(tenant_id, "tenant_id"),
            business_id=_required(business_id, "business_id"),
            goal_id=_required(goal_id, "goal_id"),
            idempotency_key=_required(idempotency_key, "idempotency_key"),
            goal_kind=_required(goal_kind, "goal_kind"),
            target_key=target_key,
            metric=metric,
            baseline=baseline,
            target=target,
            deadline_at_ms=deadline_at_ms,
            owner_id=actor,
            constraint_ids=constraint_ids,
            parent_goal_id=parent_goal_id,
            priority=priority,
            occurred_at_ms=occurred_at_ms,
            event_metadata={
                "actor_id": actor,
                "provenance": {
                    "ingress": "business_discovery",
                    "owner_confirmed": True,
                },
            },
        )
        return _jsonable_dataclass(goal)

    def list_constraints(
        self,
        *,
        tenant_id: str,
        business_id: str,
    ) -> list[dict[str, Any]]:
        if self._constraints is None:
            raise RuntimeError("canonical BusinessConstraintRegistry is not configured")
        return [
            _jsonable_dataclass(item)
            for item in self._constraints.list_for_business(
                tenant_id=_required(tenant_id, "tenant_id"),
                business_id=_required(business_id, "business_id"),
            )
        ]

    def create_constraint(
        self,
        *,
        tenant_id: str,
        business_id: str,
        actor_id: str,
        idempotency_key: str,
        confirmed: bool,
        constraint_id: str,
        constraint_kind: str,
        severity: str = "hard",
        subject_type: str | None = None,
        subject_id: str | None = None,
        state_key: str | None = None,
        comparison: str | None = None,
        threshold: float | None = None,
        occurred_at_ms: int | None = None,
    ) -> dict[str, Any]:
        if confirmed is not True:
            raise ValueError(
                "explicit owner confirmation is required for canonical constraint creation"
            )
        if self._constraints is None:
            raise RuntimeError("canonical BusinessConstraintRegistry is not configured")
        actor = _required(actor_id, "actor_id")
        constraint = self._constraints.create(
            tenant_id=_required(tenant_id, "tenant_id"),
            business_id=_required(business_id, "business_id"),
            constraint_id=_required(constraint_id, "constraint_id"),
            idempotency_key=_required(idempotency_key, "idempotency_key"),
            constraint_kind=_required(constraint_kind, "constraint_kind"),
            severity=severity,
            subject_type=subject_type,
            subject_id=subject_id,
            state_key=state_key,
            comparison=comparison,
            threshold=threshold,
            occurred_at_ms=occurred_at_ms,
            event_metadata={
                "actor_id": actor,
                "provenance": {
                    "ingress": "business_discovery",
                    "owner_confirmed": True,
                },
            },
        )
        return _jsonable_dataclass(constraint)

    def _migrate_legacy_onboarding(
        self,
        *,
        tenant_id: str,
        business_id: str,
        actor_id: str,
    ) -> None:
        if self._legacy_onboarding_reader is None or self._legacy_onboarding_migrator is None:
            return
        snapshot = self._legacy_onboarding_reader.read(
            tenant_id=tenant_id,
            user_id=actor_id,
        )
        if snapshot is None:
            return
        self._legacy_onboarding_migrator.migrate(
            settings=snapshot.settings,
            tenant_id=tenant_id,
            business_id=business_id,
            actor_id=actor_id,
            observed_at_ms=snapshot.observed_at_ms,
        )

    @staticmethod
    def _field_view(
        *,
        spec: DiscoveryFieldSpec,
        snapshot: StateSynthesizedSnapshot | None,
    ) -> dict[str, Any]:
        record = None if snapshot is None else snapshot.fields.get(spec.field_path)
        owner_asserted = _is_owner_asserted(record=record, spec=spec)
        covered = _is_covered(record)
        status = _status(record)
        return {
            "key": spec.key,
            "domain": spec.domain,
            "field_path": spec.field_path,
            "value_kind": spec.value_kind.value,
            "allowed_values": list(spec.allowed_values),
            "legacy_sources": list(spec.legacy_sources),
            "status": status,
            "covered": covered,
            "owner_asserted": owner_asserted,
            "provider_observed": _is_provider_observed(record=record, spec=spec),
            "epistemic_status": None if record is None else record.meta.get("epistemic_status"),
            "provider_key": None if record is None else record.meta.get("provider_key"),
            "value": None if record is None else record.value,
            "source": None if record is None else record.source,
            "observed_at_ms": None if record is None else record.observed_at_ms,
            "freshness_status": None if record is None else record.freshness_status,
            "conflict": False if record is None else bool(record.conflict),
            "evidence_ids": (
                []
                if record is None
                else [str(item.evidence_id) for item in record.evidence_refs]
            ),
        }


def _jsonable_dataclass(value: object) -> dict[str, Any]:
    payload = asdict(value)
    return {
        key: (
            item.value
            if hasattr(item, "value") and isinstance(item.value, str)
            else item
        )
        for key, item in payload.items()
    }


def _required(value: object, name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{name} is required")
    return normalized


def _is_owner_asserted(
    *,
    record: StateFieldRecord | None,
    spec: DiscoveryFieldSpec,
) -> bool:
    if record is None:
        return False
    return (
        str(record.meta.get("business_discovery_field_key") or "") == spec.key
        and str(record.meta.get("epistemic_status") or "") == "OWNER_ASSERTED"
    )


def _is_provider_observed(
    *,
    record: StateFieldRecord | None,
    spec: DiscoveryFieldSpec,
) -> bool:
    if record is None:
        return False
    return (
        str(record.meta.get("business_discovery_field_key") or "") == spec.key
        and str(record.meta.get("observation_role") or "") == "PROVIDER_OBSERVED"
    )


def _is_covered(record: StateFieldRecord | None) -> bool:
    return record is not None and str(record.value_kind) not in _NON_COVERING_VALUE_KINDS


def _status(record: StateFieldRecord | None) -> str:
    if record is None:
        return "missing"
    if bool(record.conflict):
        return "conflict"
    value_kind = str(record.value_kind or "")
    if value_kind == "unknown":
        return "unknown"
    if value_kind in _NON_COVERING_VALUE_KINDS:
        return value_kind
    return "known"


def _progress(fields: tuple[dict[str, Any], ...]) -> BusinessDiscoveryProgress:
    total = len(fields)
    covered = sum(1 for item in fields if bool(item["covered"]))
    owner_asserted = sum(1 for item in fields if bool(item["owner_asserted"]))
    next_key = next(
        (str(item["key"]) for item in fields if not bool(item["covered"])),
        None,
    )
    return BusinessDiscoveryProgress(
        total_fields=total,
        covered_fields=covered,
        owner_asserted_fields=owner_asserted,
        remaining_fields=max(0, total - covered),
        complete=covered == total,
        next_field_key=next_key,
    )


def _provider_result_payload(result: ProviderObservationIngressResult) -> dict[str, Any]:
    return {
        "evidence_id": result.evidence_id,
        "state_id": result.state_id,
        "observed_fields": list(result.observed_fields),
        "verified_fields": list(result.verified_fields),
        "conflicted_fields": list(result.conflicted_fields),
        "replayed": result.replayed,
    }


def _result_payload(result: OwnerAssertionIngressResult) -> dict[str, Any]:
    return {
        "fact_id": result.fact_id,
        "evidence_id": result.evidence_id,
        "state_id": result.state_id,
        "field_path": result.field_path,
        "replayed": result.replayed,
    }


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
        if isinstance(margin, bool) or not isinstance(margin, int | float):
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
                idempotency_key=(
                    f"{_MIGRATION_NAMESPACE}:{int(observed_at_ms)}:{item.field_key}"
                ),
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
    "CANON_BUSINESS_DISCOVERY_WORKSPACE",
    "BusinessDiscoveryProgress",
    "BusinessDiscoveryWorkspace",
    "LegacyOnboardingEventReader",
    "LegacyOnboardingField",
    "LegacyOnboardingMigrationResult",
    "LegacyOnboardingMigrator",
    "LegacyOnboardingSnapshot",
    "legacy_onboarding_fields",
]
