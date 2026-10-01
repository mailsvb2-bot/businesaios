from __future__ import annotations

import pytest

from application.business_discovery.legacy_onboarding_migration import (
    LegacyOnboardingMigrator,
    legacy_onboarding_fields,
)
from application.business_discovery.owner_assertion_ingress import OwnerBusinessAssertionIngress
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
