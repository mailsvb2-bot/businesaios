from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from runtime._internal.effects_actions import offer_patch_actions


class FakeEventLog:
    def __init__(self, *, tenant_id: str = "business-a", fail_emit: bool = False) -> None:
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
    monkeypatch.setattr(
        offer_patch_actions,
        "resolve_offer_catalog",
        lambda **_kwargs: ("business-a:crm-pro:test", path),
    )


def _apply(effects: FakeEffects, *, mode: str, notify_user_id: str | None = None):
    return effects.apply_offer_patch(
        decision_id="decision-offer-patch",
        correlation_id="correlation-offer-patch",
        tenant_id="business-a",
        product="crm-pro",
        env="test",
        offer_id="offer-1",
        patch={"headline": "New title"},
        mode=mode,
        notify_user_id=notify_user_id,
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
def test_audit_failure_restores_live_catalog_and_previous_backup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = tmp_path / "offers.yaml"
    backup = catalog.with_suffix(".yaml.bak")
    original = _catalog_text()
    previous_backup = "previous_backup: true\n"
    catalog.write_text(original, encoding="utf-8")
    backup.write_text(previous_backup, encoding="utf-8")
    _bind_catalog(monkeypatch, catalog)
    effects = FakeEffects(FakeEventLog(fail_emit=True))

    with pytest.raises(RuntimeError, match="simulated audit failure"):
        _apply(effects, mode="apply")

    assert catalog.read_text(encoding="utf-8") == original
    assert backup.read_text(encoding="utf-8") == previous_backup


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

    result = _apply(effects, mode="apply", notify_user_id="owner-1")

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
        "scope": "business-a:crm-pro:test",
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
    effects = FakeEffects(FakeEventLog(tenant_id="business-b"))

    with pytest.raises(RuntimeError, match="TENANT_CONTEXT_MISMATCH"):
        _apply(effects, mode="apply")

    assert catalog.read_text(encoding="utf-8") == original
    assert effects.event_log.events == []
