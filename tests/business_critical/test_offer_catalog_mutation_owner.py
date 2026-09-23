from pathlib import Path

import pytest
import yaml

from runtime._internal.effects_actions import offer_patch_actions
from runtime._internal.effects_domains.admin_pricing import prepare_offer_price_update
from runtime._internal.effects_domains.admin_state_support import (
    apply_pricing_change_effect,
)
from runtime.platform.event_store.memory_event_store import MemoryEventStore


class _EventLog:
    tenant_id = "business-a"

    def __init__(self) -> None:
        self.events: list[dict] = []

    def emit(self, **event):
        self.events.append(dict(event))
        return {"event_id": "event-1", **dict(event)}


class _Effects(offer_patch_actions.OfferPatchEffectsMixin):
    def __init__(self) -> None:
        self.event_log = _EventLog()
        self.event_store = MemoryEventStore()

    def send_message(self, **kwargs):
        return {"ok": True, "kwargs": dict(kwargs)}


def _write_catalog(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "catalog_id": "business-a:crm-pro:test",
                "pricing_version": "version-1",
                "offers": [
                    {
                        "offer_id": "offer-1",
                        "base_price_rub": 100,
                        "rules": {},
                        "variants": {"a": {"title": "Old title", "body": "Body"}},
                    }
                ],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )


@pytest.mark.lock
def test_pricing_and_offer_patch_share_one_catalog_mutation_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = tmp_path / "business-a" / "crm-pro" / "test.yaml"
    _write_catalog(catalog)
    pricing = prepare_offer_price_update(
        tenant_id="business-a",
        product_id="crm-pro",
        environment="test",
        offer_id="offer-1",
        new_price=200,
        pricing_version="version-2",
        catalog_path=catalog,
        lock_timeout_s=0.2,
    )
    monkeypatch.setenv("OFFER_CATALOG_MUTATION_LOCK_TIMEOUT_S", "0.05")
    monkeypatch.setattr(offer_patch_actions, "assert_called_from_executor", lambda: None)
    monkeypatch.setattr(
        offer_patch_actions,
        "resolve_offer_catalog_write",
        lambda **_kwargs: ("business-a:scope-a:crm-pro:test", catalog, catalog),
    )
    effects = _Effects()
    try:
        with pytest.raises(RuntimeError, match="CATALOG_MUTATION_LOCK_TIMEOUT"):
            effects.apply_offer_patch(
                decision_id="decision-1",
                correlation_id="correlation-1",
                tenant_id="business-a",
                business_id="scope-a",
                product="crm-pro",
                env="test",
                offer_id="offer-1",
                patch={"headline": "New title"},
                mode="apply",
            )
    finally:
        pricing.finalize()

    current = yaml.safe_load(catalog.read_text(encoding="utf-8"))
    assert current["pricing_version"] == "version-1"
    assert current["offers"][0]["base_price_rub"] == 100
    assert current["offers"][0]["variants"]["a"]["title"] == "Old title"
    assert effects.event_log.events == []


@pytest.mark.lock
def test_business_scoped_offer_patch_copy_on_write_never_mutates_legacy_catalog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path / "offer_catalogs"
    legacy = data_dir / "tenant-a" / "crm-pro" / "test.yaml"
    _write_catalog(legacy)
    original = legacy.read_bytes()
    monkeypatch.setenv("OFFER_CATALOGS_DATA_DIR", str(data_dir))
    monkeypatch.setattr(offer_patch_actions, "assert_called_from_executor", lambda: None)

    effects = _Effects()
    effects.event_log.tenant_id = "tenant-a"
    effects.apply_offer_patch(
        decision_id="decision-a",
        correlation_id="correlation-a",
        tenant_id="tenant-a",
        business_id="business-a",
        product="crm-pro",
        env="test",
        offer_id="offer-1",
        patch={"headline": "Business A"},
        mode="apply",
    )
    effects.apply_offer_patch(
        decision_id="decision-b",
        correlation_id="correlation-b",
        tenant_id="tenant-a",
        business_id="business-b",
        product="crm-pro",
        env="test",
        offer_id="offer-1",
        patch={"headline": "Business B"},
        mode="apply",
    )

    business_a = data_dir / "tenant-a" / "business-a" / "crm-pro" / "test.yaml"
    business_b = data_dir / "tenant-a" / "business-b" / "crm-pro" / "test.yaml"
    assert legacy.read_bytes() == original
    assert yaml.safe_load(business_a.read_text(encoding="utf-8"))["offers"][0]["variants"]["a"]["title"] == "Business A"
    assert yaml.safe_load(business_b.read_text(encoding="utf-8"))["offers"][0]["variants"]["a"]["title"] == "Business B"


@pytest.mark.lock
def test_business_scoped_pricing_copy_on_write_never_mutates_legacy_catalog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path / "offer_catalogs"
    legacy = data_dir / "tenant-a" / "crm-pro" / "test.yaml"
    _write_catalog(legacy)
    original = legacy.read_bytes()
    monkeypatch.setenv("OFFER_CATALOGS_DATA_DIR", str(data_dir))

    transaction = prepare_offer_price_update(
        tenant_id="tenant-a",
        business_id="business-a",
        product_id="crm-pro",
        environment="test",
        offer_id="offer-1",
        new_price=250,
        pricing_version="version-2",
    )
    try:
        result = transaction.apply()
    finally:
        transaction.finalize()

    business = data_dir / "tenant-a" / "business-a" / "crm-pro" / "test.yaml"
    assert legacy.read_bytes() == original
    current = yaml.safe_load(business.read_text(encoding="utf-8"))
    assert current["offers"][0]["base_price_rub"] == 250
    assert result["business_id"] == "business-a"
    assert result["catalog_id"] == "tenant-a:business-a:crm-pro:test"


@pytest.mark.lock
def test_failed_first_patch_removes_materialized_business_catalog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path / "offer_catalogs"
    legacy = data_dir / "tenant-a" / "crm-pro" / "test.yaml"
    _write_catalog(legacy)
    original = legacy.read_bytes()
    monkeypatch.setenv("OFFER_CATALOGS_DATA_DIR", str(data_dir))
    monkeypatch.setattr(offer_patch_actions, "assert_called_from_executor", lambda: None)

    effects = _Effects()
    effects.event_log.tenant_id = "tenant-a"
    effects.event_store = None

    with pytest.raises(RuntimeError, match="OFFER_EVENT_STORE_REQUIRED"):
        effects.apply_offer_patch(
            decision_id="decision-fail",
            correlation_id="correlation-fail",
            tenant_id="tenant-a",
            business_id="business-a",
            product="crm-pro",
            env="test",
            offer_id="offer-1",
            patch={"headline": "Must not survive"},
            mode="apply",
        )

    business = data_dir / "tenant-a" / "business-a" / "crm-pro" / "test.yaml"
    assert not business.exists()
    assert legacy.read_bytes() == original


@pytest.mark.lock
def test_failed_first_pricing_event_projection_removes_materialized_business_catalog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path / "offer_catalogs"
    legacy = data_dir / "tenant-a" / "crm-pro" / "test.yaml"
    _write_catalog(legacy)
    original = legacy.read_bytes()
    monkeypatch.setenv("OFFER_CATALOGS_DATA_DIR", str(data_dir))

    effects = _Effects()
    effects.event_log.tenant_id = "tenant-a"
    effects.event_store = None

    with pytest.raises(RuntimeError, match="OFFER_EVENT_STORE_REQUIRED"):
        apply_pricing_change_effect(
            effects,
            decision_id="decision-pricing-fail",
            correlation_id="correlation-pricing-fail",
            admin_id="approver-1",
            tenant_id="tenant-a",
            business_id="business-a",
            product_id="crm-pro",
            environment="test",
            offer_id="offer-1",
            new_price=250,
            pricing_version="version-2",
            request_id="request-pricing-fail",
            requested_by="requester-1",
        )

    business = data_dir / "tenant-a" / "business-a" / "crm-pro" / "test.yaml"
    assert not business.exists()
    assert legacy.read_bytes() == original


@pytest.mark.lock
def test_successful_legacy_noop_does_not_materialize_business_shadow(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path / "offer_catalogs"
    legacy = data_dir / "tenant-a" / "crm-pro" / "test.yaml"
    _write_catalog(legacy)
    raw = yaml.safe_load(legacy.read_text(encoding="utf-8"))
    raw["offers"][0]["variants"]["a"]["title"] = "New title"
    legacy.write_text(
        yaml.safe_dump(raw, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    original = legacy.read_bytes()
    monkeypatch.setenv("OFFER_CATALOGS_DATA_DIR", str(data_dir))
    monkeypatch.setattr(offer_patch_actions, "assert_called_from_executor", lambda: None)

    effects = _Effects()
    effects.event_log.tenant_id = "tenant-a"
    result = effects.apply_offer_patch(
        decision_id="decision-noop",
        correlation_id="correlation-noop",
        tenant_id="tenant-a",
        business_id="business-a",
        product="crm-pro",
        env="test",
        offer_id="offer-1",
        patch={"headline": "New title"},
        mode="apply",
    )

    business = data_dir / "tenant-a" / "business-a" / "crm-pro" / "test.yaml"
    assert result["status"] == "verified"
    assert result["changed"] is False
    assert not business.exists()
    assert legacy.read_bytes() == original
    assert list(
        effects.event_store.iter_events(
            tenant_id="tenant-a",
            start_ms=0,
        )
    ) == []
