from __future__ import annotations

import pytest

from application.business_discovery.legacy_onboarding_migration import (
    LegacyOnboardingEventReader,
    LegacyOnboardingMigrator,
    legacy_onboarding_fields,
)
from application.business_discovery.owner_assertion_ingress import OwnerBusinessAssertionIngress
from application.business_discovery.workspace import BusinessDiscoveryWorkspace
from contracts.event_store import BUSINESS_FACT_EVENT_TYPE
from reliability.idempotency_store import InMemoryIdempotencyStore
from runtime.platform.event_store.memory_event_store import MemoryEventStore
from runtime.state import StateSynthesisEngine
from runtime.state.state_snapshot_store import FileStateSnapshotStore
from storage.evidence_store import InMemoryEvidenceStore


def _by_key(settings):
    return {item.field_key: item.value for item in legacy_onboarding_fields(settings)}


def test_legacy_onboarding_full_session_maps_only_existing_canonical_fields() -> None:
    settings = {
        "autopilot:session": {
            "stage": "pick:offer",
            "diag": {
                "what": "Подписка для салонов",
                "avg_check_minor": 125_000,
                "currency": "rub",
                "margin_pct": 32,
                "region": "Нижний Новгород",
                "has_clients": "some",
                "budget_minor_7d": 50_000,
                "budget_currency": "eur",
            },
        }
    }

    assert _by_key(settings) == {
        "offer.summary": "Подписка для салонов",
        "market.region": "Нижний Новгород",
        "economics.average_check": {"amount_minor": 125_000, "currency": "RUB"},
        "economics.margin_pct": 32,
        "sales.has_clients": "some",
        "acquisition.test_budget_7d": {"amount_minor": 50_000, "currency": "EUR"},
    }


def test_legacy_dataclass_defaults_are_not_promoted_before_question_was_answered() -> None:
    settings = {
        "autopilot:session": {
            "stage": "diag:avg_check",
            "diag": {
                "what": "Консалтинг",
                "avg_check_minor": 0,
                "currency": "RUB",
                "margin_pct": 0,
                "region": "",
                "has_clients": "unknown",
                "budget_minor_7d": 0,
                "budget_currency": "EUR",
            },
        }
    }

    assert _by_key(settings) == {"offer.summary": "Консалтинг"}


def test_current_telegram_legacy_aliases_migrate_without_inventing_new_truth() -> None:
    settings = {
        "autopilot:session": {
            "stage": "pick:offer",
            "diag": {
                "what": "Сервис аналитики",
                "avg_check_rub": 4900,
                "margin_pct": 25,
                "leads_per_day": 7,
                "offer": "offer-1",
                "channel": "internal",
            },
        }
    }

    assert _by_key(settings) == {
        "offer.summary": "Сервис аналитики",
        "economics.average_check": {"amount_minor": 490_000, "currency": "RUB"},
        "economics.margin_pct": 25,
    }


def test_legacy_migration_writes_through_canonical_fact_evidence_state_and_replays(tmp_path) -> None:
    state = StateSynthesisEngine(
        snapshot_store=FileStateSnapshotStore(tmp_path / "state")
    )
    events = MemoryEventStore()
    ingress = OwnerBusinessAssertionIngress(
        event_store=events,
        evidence_store=InMemoryEvidenceStore(),
        state_engine=state,
        idempotency_store=InMemoryIdempotencyStore(),
    )
    migrator = LegacyOnboardingMigrator(ingress=ingress)
    settings = {
        "autopilot:session": {
            "stage": "running",
            "diag": {
                "what": "B2B подписка",
                "avg_check_rub": 7500,
                "margin_pct": 40,
            },
        }
    }

    first = migrator.migrate(
        settings=settings,
        tenant_id="tenant-1",
        business_id="business-1",
        actor_id="owner-1",
        observed_at_ms=1_700_000_000_000,
        recorded_at_ms=1_700_000_000_100,
    )
    assert first.migrated == (
        "offer.summary",
        "economics.average_check",
        "economics.margin_pct",
    )
    snapshot = state.snapshot_store.load_latest(
        tenant_id="tenant-1",
        business_id="business-1",
    )
    assert snapshot is not None
    assert snapshot.fields["business.offer.summary"].value == "B2B подписка"
    assert snapshot.fields["business.economics.average_check"].value == {
        "amount_minor": 750_000,
        "currency": "RUB",
    }
    assert snapshot.fields["business.economics.margin_pct"].value == 40

    replay = migrator.migrate(
        settings=settings,
        tenant_id="tenant-1",
        business_id="business-1",
        actor_id="owner-1",
        observed_at_ms=1_700_000_000_000,
        recorded_at_ms=1_700_000_000_100,
    )
    assert replay.migrated == first.migrated
    assert all(item.replayed for item in replay.assertions)

    changed = {
        "autopilot:session": {
            "stage": "running",
            "diag": {
                "what": "Другая бизнес-истина",
                "avg_check_rub": 7500,
                "margin_pct": 40,
            },
        }
    }
    with pytest.raises(ValueError, match="idempotency key"):
        migrator.migrate(
            settings=changed,
            tenant_id="tenant-1",
            business_id="business-1",
            actor_id="owner-1",
            observed_at_ms=1_700_000_000_000,
            recorded_at_ms=1_700_000_000_100,
        )


@pytest.mark.parametrize(
    "diag",
    [
        {"avg_check_rub": -1},
        {"avg_check_rub": True},
        {"has_clients": "maybe"},
        {"margin_pct": "forty"},
    ],
)
def test_legacy_migration_fails_closed_on_recognized_invalid_business_values(diag) -> None:
    with pytest.raises(ValueError):
        legacy_onboarding_fields(
            {"autopilot:session": {"stage": "running", "diag": diag}}
        )



def _legacy_setting_event(*, tenant_id: str, user_id: str, timestamp_ms: int, what: str) -> dict:
    return {
        "event_id": f"legacy-setting:{tenant_id}:{user_id}:{timestamp_ms}",
        "tenant_id": tenant_id,
        "user_id": user_id,
        "source": "user_state",
        "event_type": "user_setting_set",
        "timestamp_ms": timestamp_ms,
        "decision_id": "legacy-decision",
        "correlation_id": "legacy-correlation",
        "payload": {
            "tenant_id": tenant_id,
            "key": "autopilot:session",
            "value": {
                "stage": "running",
                "diag": {
                    "what": what,
                    "avg_check_rub": 5200,
                    "margin_pct": 35,
                },
            },
        },
    }


def test_legacy_event_reader_selects_latest_exact_tenant_user_snapshot() -> None:
    events = MemoryEventStore()
    events.append_event(
        _legacy_setting_event(
            tenant_id="tenant-1",
            user_id="owner-1",
            timestamp_ms=1_700_000_000_000,
            what="Старое значение",
        )
    )
    events.append_event(
        _legacy_setting_event(
            tenant_id="tenant-1",
            user_id="other-owner",
            timestamp_ms=1_700_000_000_500,
            what="Чужой пользователь",
        )
    )
    events.append_event(
        _legacy_setting_event(
            tenant_id="tenant-2",
            user_id="owner-1",
            timestamp_ms=1_700_000_000_600,
            what="Чужой tenant",
        )
    )
    events.append_event(
        _legacy_setting_event(
            tenant_id="tenant-1",
            user_id="owner-1",
            timestamp_ms=1_700_000_001_000,
            what="Актуальное значение",
        )
    )

    snapshot = LegacyOnboardingEventReader(event_store=events).read(
        tenant_id="tenant-1",
        user_id="owner-1",
    )

    assert snapshot is not None
    assert snapshot.observed_at_ms == 1_700_000_001_000
    assert snapshot.settings["autopilot:session"]["diag"]["what"] == "Актуальное значение"


def test_legacy_event_reader_respects_latest_explicit_session_clear() -> None:
    events = MemoryEventStore()
    events.append_event(
        _legacy_setting_event(
            tenant_id="tenant-1",
            user_id="owner-1",
            timestamp_ms=1_700_000_000_000,
            what="Старое значение",
        )
    )
    cleared = _legacy_setting_event(
        tenant_id="tenant-1",
        user_id="owner-1",
        timestamp_ms=1_700_000_001_000,
        what="ignored",
    )
    cleared["payload"]["value"] = None
    events.append_event(cleared)

    assert (
        LegacyOnboardingEventReader(event_store=events).read(
            tenant_id="tenant-1",
            user_id="owner-1",
        )
        is None
    )


def test_authenticated_workspace_read_migrates_durable_legacy_session_once(tmp_path) -> None:
    events = MemoryEventStore()
    events.append_event(
        _legacy_setting_event(
            tenant_id="tenant-1",
            user_id="owner-1",
            timestamp_ms=1_700_000_000_000,
            what="Legacy B2B offer",
        )
    )
    state = StateSynthesisEngine(
        snapshot_store=FileStateSnapshotStore(tmp_path / "state")
    )
    ingress = OwnerBusinessAssertionIngress(
        event_store=events,
        evidence_store=InMemoryEvidenceStore(),
        state_engine=state,
        idempotency_store=InMemoryIdempotencyStore(),
    )
    workspace = BusinessDiscoveryWorkspace(
        ingress=ingress,
        state_engine=state,
        legacy_onboarding_reader=LegacyOnboardingEventReader(event_store=events),
        legacy_onboarding_migrator=LegacyOnboardingMigrator(ingress=ingress),
    )

    first = workspace.describe(
        tenant_id="tenant-1",
        business_id="business-1",
        actor_id="owner-1",
    )
    offer = next(item for item in first["fields"] if item["key"] == "offer.summary")
    average_check = next(
        item for item in first["fields"] if item["key"] == "economics.average_check"
    )
    assert offer["value"] == "Legacy B2B offer"
    assert offer["owner_asserted"] is True
    assert offer["observed_at_ms"] == 1_700_000_000_000
    assert average_check["value"] == {"amount_minor": 520_000, "currency": "RUB"}

    second = workspace.describe(
        tenant_id="tenant-1",
        business_id="business-1",
        actor_id="owner-1",
    )
    assert second["state_id"] == first["state_id"]

    owner_facts = [
        event
        for event in events.iter_events(
            tenant_id="tenant-1",
            start_ms=0,
            event_type=BUSINESS_FACT_EVENT_TYPE,
        )
        if str(event.get("source") or "") == "business_discovery.owner_assertion"
    ]
    assert len(owner_facts) == 3


def test_workspace_does_not_migrate_another_users_legacy_session(tmp_path) -> None:
    events = MemoryEventStore()
    events.append_event(
        _legacy_setting_event(
            tenant_id="tenant-1",
            user_id="other-owner",
            timestamp_ms=1_700_000_000_000,
            what="Чужая бизнес-истина",
        )
    )
    state = StateSynthesisEngine(
        snapshot_store=FileStateSnapshotStore(tmp_path / "state")
    )
    ingress = OwnerBusinessAssertionIngress(
        event_store=events,
        evidence_store=InMemoryEvidenceStore(),
        state_engine=state,
        idempotency_store=InMemoryIdempotencyStore(),
    )
    workspace = BusinessDiscoveryWorkspace(
        ingress=ingress,
        state_engine=state,
        legacy_onboarding_reader=LegacyOnboardingEventReader(event_store=events),
        legacy_onboarding_migrator=LegacyOnboardingMigrator(ingress=ingress),
    )

    view = workspace.describe(
        tenant_id="tenant-1",
        business_id="business-1",
        actor_id="owner-1",
    )

    offer = next(item for item in view["fields"] if item["key"] == "offer.summary")
    assert offer["value"] is None
    assert offer["covered"] is False
