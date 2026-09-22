from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from core.events.event_types import OFFER_CREATED, OFFER_UPDATED
from runtime._internal.effects_actions import offer_patch_actions
from runtime.platform.event_store.memory_event_store import MemoryEventStore


class FakeEventLog:
    def __init__(self, *, tenant_id: str = "tenant-a", fail_emit: bool = False) -> None:
        self.tenant_id = tenant_id
        self.fail_emit = fail_emit
        self.events: list[dict] = []

    def emit(self, **event):
        if self.fail_emit:
            raise RuntimeError("simulated audit failure")
        row = {
            "event_id": f"event-{len(self.events) + 1}",
            "tenant_id": self.tenant_id,
            **dict(event),
        }
        self.events.append(row)
        return row


class FakeEffects(offer_patch_actions.OfferPatchEffectsMixin):
    def __init__(self, event_log: FakeEventLog) -> None:
        self.event_log = event_log
        self.event_store = MemoryEventStore()
        self.messages: list[dict] = []
        self.fail_notification = False

    def send_message(self, **kwargs):
        self.messages.append(dict(kwargs))
        if self.fail_notification:
            raise RuntimeError("simulated notification failure")
        return {
            "ok": True,
            "evidence": {
                "source": "connector",
                "verified": True,
                "status": "verified",
                "external_refs": ["message-1"],
                "confidence": 1.0,
            },
        }


def _catalog_text(title: str = "Old title") -> str:
    return yaml.safe_dump(
        {
            "offers": [
                {
                    "offer_id": "offer-1",
                    "variants": {
                        "a": {
                            "title": title,
                            "body": "Body",
                        }
                    },
                }
            ]
        },
        sort_keys=False,
        allow_unicode=True,
    )


@pytest.fixture(autouse=True)
def _disable_executor_guard(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(offer_patch_actions, "assert_called_from_executor", lambda: None)


def _bind_catalog(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    scope = "tenant-a:business-a:crm-pro:test"
    monkeypatch.setattr(
        offer_patch_actions,
        "resolve_offer_catalog",
        lambda **_kwargs: (scope, path),
    )
    monkeypatch.setattr(
        offer_patch_actions,
        "resolve_offer_catalog_write",
        lambda **_kwargs: (scope, path, path),
    )


def _apply(
    effects: FakeEffects,
    *,
    mode: str,
    notify_user_id: str | None = None,
    channel: str = "telegram",
    channel_policy: dict | None = None,
):
    return effects.apply_offer_patch(
        decision_id="decision-offer-patch",
        correlation_id="correlation-offer-patch",
        tenant_id="tenant-a",
        business_id="business-a",
        product="crm-pro",
        env="test",
        offer_id="offer-1",
        patch={"headline": "New title"},
        mode=mode,
        notify_user_id=notify_user_id,
        channel=channel,
        channel_policy=channel_policy,
    )


@pytest.mark.lock
def test_dry_run_never_changes_catalog_or_emits_mutation_proof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = tmp_path / "offers.yaml"
    original = _catalog_text()
    catalog.write_text(original, encoding="utf-8")
    _bind_catalog(monkeypatch, catalog)
    effects = FakeEffects(FakeEventLog())

    result = _apply(effects, mode="dry_run")

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["changed"] is True
    assert "router_evidence" not in result
    assert catalog.read_text(encoding="utf-8") == original
    assert effects.event_log.events == []
    assert not catalog.with_suffix(".yaml.bak").exists()


@pytest.mark.lock
def test_apply_writes_catalog_backup_and_real_event_id_proof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = tmp_path / "offers.yaml"
    original = _catalog_text()
    catalog.write_text(original, encoding="utf-8")
    _bind_catalog(monkeypatch, catalog)
    effects = FakeEffects(FakeEventLog())

    result = _apply(effects, mode="apply")

    written = yaml.safe_load(catalog.read_text(encoding="utf-8"))
    assert written["offers"][0]["variants"]["a"]["title"] == "New title"
    assert catalog.with_suffix(".yaml.bak").read_text(encoding="utf-8") == original
    assert result["status"] == "verified"
    assert result["router_evidence"]["source"] == "ledger"
    assert result["router_evidence"]["external_refs"] == ["event-1"]
    assert effects.event_log.events[-1]["event_type"] == "offer_patch_applied@v1"


@pytest.mark.lock
def test_audit_failure_after_event_spine_commit_keeps_canonical_offer_and_retry_repairs_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = tmp_path / "offers.yaml"
    original = _catalog_text()
    catalog.write_text(original, encoding="utf-8")
    _bind_catalog(monkeypatch, catalog)
    event_log = FakeEventLog(fail_emit=True)
    effects = FakeEffects(event_log)

    with pytest.raises(RuntimeError, match="simulated audit failure"):
        _apply(effects, mode="apply")

    written = yaml.safe_load(catalog.read_text(encoding="utf-8"))
    assert written["offers"][0]["variants"]["a"]["title"] == "New title"
    spine_rows = list(
        effects.event_store.iter_events(
            tenant_id="tenant-a",
            start_ms=0,
            event_type=OFFER_UPDATED,
        )
    )
    assert len(spine_rows) == 1

    event_log.fail_emit = False
    result = _apply(effects, mode="apply")
    assert result["status"] == "verified"
    spine_rows = list(
        effects.event_store.iter_events(
            tenant_id="tenant-a",
            start_ms=0,
            event_type=OFFER_UPDATED,
        )
    )
    assert len(spine_rows) == 1
    assert event_log.events[-1]["event_type"] == "offer_patch_applied@v1"


@pytest.mark.lock
def test_notification_failure_cannot_replay_verified_catalog_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = tmp_path / "offers.yaml"
    catalog.write_text(_catalog_text(), encoding="utf-8")
    _bind_catalog(monkeypatch, catalog)
    effects = FakeEffects(FakeEventLog())
    effects.fail_notification = True

    policy = {"fallback_channels": ["email", "sms"]}
    result = _apply(
        effects,
        mode="apply",
        notify_user_id="owner-1",
        channel="whatsapp",
        channel_policy=policy,
    )

    assert effects.messages[-1]["channel"] == "whatsapp"
    assert effects.messages[-1]["channel_policy"] == policy
    assert effects.messages[-1]["channel_policy"] is not policy
    assert result["ok"] is True
    assert result["status"] == "verified"
    assert result["notification"]["ok"] is False
    assert result["notification"]["status"] == "notification_failed"
    assert result["router_evidence"]["external_refs"] == ["event-1"]


@pytest.mark.lock
def test_rollback_without_backup_is_an_explicit_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = tmp_path / "offers.yaml"
    catalog.write_text(_catalog_text(), encoding="utf-8")
    _bind_catalog(monkeypatch, catalog)
    effects = FakeEffects(FakeEventLog())

    result = _apply(effects, mode="rollback")

    assert result == {
        "ok": False,
        "status": "failed",
        "reason": "offer_patch_backup_missing",
        "mode": "rollback",
        "scope": "tenant-a:business-a:crm-pro:test",
        "offer_id": "offer-1",
    }
    assert effects.event_log.events == []


@pytest.mark.lock
def test_cross_tenant_offer_patch_fails_before_file_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = tmp_path / "offers.yaml"
    original = _catalog_text()
    catalog.write_text(original, encoding="utf-8")
    _bind_catalog(monkeypatch, catalog)
    effects = FakeEffects(FakeEventLog(tenant_id="tenant-b"))

    with pytest.raises(RuntimeError, match="TENANT_CONTEXT_MISMATCH"):
        _apply(effects, mode="apply")

    assert catalog.read_text(encoding="utf-8") == original
    assert effects.event_log.events == []


@pytest.mark.lock
def test_created_offer_retry_reuses_created_event_and_preserves_original_backup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = tmp_path / "offers.yaml"
    original = yaml.safe_dump({"offers": []}, sort_keys=False, allow_unicode=True)
    catalog.write_text(original, encoding="utf-8")
    _bind_catalog(monkeypatch, catalog)
    event_log = FakeEventLog(fail_emit=True)
    effects = FakeEffects(event_log)

    with pytest.raises(RuntimeError, match="simulated audit failure"):
        _apply(effects, mode="apply")

    backup = catalog.with_suffix(".yaml.bak")
    assert backup.read_text(encoding="utf-8") == original
    created = list(
        effects.event_store.iter_events(
            tenant_id="tenant-a",
            start_ms=0,
            event_type=OFFER_CREATED,
        )
    )
    updated = list(
        effects.event_store.iter_events(
            tenant_id="tenant-a",
            start_ms=0,
            event_type=OFFER_UPDATED,
        )
    )
    assert len(created) == 1
    assert updated == []

    event_log.fail_emit = False
    result = _apply(effects, mode="apply")

    assert result["changed"] is False
    assert result["router_evidence"]["payload"]["replayed_event_spine"] is True
    assert backup.read_text(encoding="utf-8") == original
    created = list(
        effects.event_store.iter_events(
            tenant_id="tenant-a",
            start_ms=0,
            event_type=OFFER_CREATED,
        )
    )
    updated = list(
        effects.event_store.iter_events(
            tenant_id="tenant-a",
            start_ms=0,
            event_type=OFFER_UPDATED,
        )
    )
    assert len(created) == 1
    assert updated == []
