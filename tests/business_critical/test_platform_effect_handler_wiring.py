from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.actions.catalog import build_catalog
from runtime.boot.actions_registry import INLINE_ALLOWLIST, get_spec
from runtime.boot.handler_groups.ops import register_ops_handlers
from runtime.effects import registry as legacy_effect_registry
from runtime.execution import executor_state as executor_state_module
from runtime.handlers import ActionHandlerRegistry
from runtime.handlers.platform_effects import (
    handle_apply_offer_patch,
    handle_suggest_offer_patch,
)
from runtime.security.capability_gate import (
    GuardedEffectsPort,
    clear_effect_capability,
    set_effect_capability,
)


PLATFORM_ACTIONS = {
    "enqueue_evolution_job@v1",
    "apply_offer_patch@v1",
    "suggest_offer_patch@v1",
}


class FakePlatformEffects:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.suggestion_notification: object = None

    def apply_offer_patch(self, **kwargs):
        self.calls.append(dict(kwargs))
        return {"ok": True, "mode": kwargs["mode"]}

    def suggest_offer_patch(self, **kwargs):
        self.calls.append(dict(kwargs))
        return {
            "ok": True,
            "status": "advisory",
            "patch": {"headline": "New title"},
            "notification": self.suggestion_notification,
        }


def _env() -> SimpleNamespace:
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-platform",
            correlation_id="correlation-platform",
        )
    )


def _suggest_payload(*, notify_user_id: str | None = None) -> dict[str, str]:
    payload = {
        "tenant_id": "business-a",
        "business_id": "business-a",
        "product": "crm-pro",
        "env": "test",
        "offer_id": "offer-1",
        "action": "improve_copy",
    }
    if notify_user_id:
        payload["notify_user_id"] = notify_user_id
    return payload


@pytest.mark.lock
def test_platform_effect_actions_are_real_canonical_handlers() -> None:
    handlers = ActionHandlerRegistry()

    register_ops_handlers(
        handlers=handlers,
        event_store=object(),
    )

    assert PLATFORM_ACTIONS.issubset(handlers.all_actions())
    for action in PLATFORM_ACTIONS:
        spec = get_spec(action)
        assert spec.handler_ref.startswith("runtime.handlers.platform_effects:")
        assert action not in INLINE_ALLOWLIST


@pytest.mark.lock
def test_offer_patch_schema_allows_rollback_without_dummy_patch() -> None:
    schema = build_catalog()["apply_offer_patch@v1"].schema

    assert "patch" not in schema.required
    assert "patch" in schema.optional
    schema.validate(
        {
            "tenant_id": "business-a",
            "business_id": "business-a",
            "product": "crm-pro",
            "env": "test",
            "offer_id": "offer-1",
            "mode": "rollback",
        }
    )


@pytest.mark.lock
def test_offer_patch_handler_requires_patch_only_for_preview_and_apply() -> None:
    effects = FakePlatformEffects()
    base = {
        "tenant_id": "business-a",
        "business_id": "business-a",
        "product": "crm-pro",
        "env": "test",
        "offer_id": "offer-1",
    }

    rollback = handle_apply_offer_patch(
        {**base, "mode": "rollback"},
        effects,
        _env(),
    )

    assert rollback == {"ok": True, "mode": "rollback"}
    assert effects.calls[-1]["patch"] == {}
    assert effects.calls[-1]["decision_id"] == "decision-platform"
    assert effects.calls[-1]["correlation_id"] == "correlation-platform"

    for mode in ("dry_run", "apply"):
        with pytest.raises(ValueError, match="OFFER_PATCH_REQUIRED"):
            handle_apply_offer_patch(
                {**base, "mode": mode},
                effects,
                _env(),
            )

    with pytest.raises(ValueError, match="INVALID_OFFER_PATCH_MODE"):
        handle_apply_offer_patch(
            {**base, "mode": "unknown"},
            effects,
            _env(),
        )


@pytest.mark.lock
def test_offer_suggestion_without_notification_remains_advisory_result() -> None:
    effects = FakePlatformEffects()

    result = handle_suggest_offer_patch(
        _suggest_payload(),
        effects,
        _env(),
    )

    assert result["ok"] is True
    assert result["status"] == "advisory"
    assert "router_evidence" not in result


@pytest.mark.lock
def test_offer_suggestion_notification_promotes_only_positive_connector_proof() -> None:
    effects = FakePlatformEffects()
    effects.suggestion_notification = {
        "ok": True,
        "evidence": {
            "source": "connector",
            "verified": True,
            "status": "verified",
            "external_refs": ["message-offer-suggestion-1"],
            "confidence": 1.0,
        },
    }

    result = handle_suggest_offer_patch(
        _suggest_payload(notify_user_id="owner-1"),
        effects,
        _env(),
    )

    assert result["ok"] is True
    assert result["status"] == "verified"
    assert result["router_evidence"]["source"] == "connector"
    assert result["router_evidence"]["external_refs"] == [
        "message-offer-suggestion-1"
    ]

    effects.suggestion_notification = {
        "ok": False,
        "status": "notification_failed",
    }
    failed = handle_suggest_offer_patch(
        _suggest_payload(notify_user_id="owner-1"),
        effects,
        _env(),
    )

    assert failed["ok"] is False
    assert failed["status"] == "failed"
    assert failed["router_evidence"] is None


@pytest.mark.lock
def test_legacy_parallel_effect_registry_is_removed_fail_closed() -> None:
    assert legacy_effect_registry.CANON_LEGACY_EFFECT_REGISTRY_REMOVED is True

    with pytest.raises(
        RuntimeError,
        match="LEGACY_EFFECT_ACTION_REGISTRY_REMOVED",
    ):
        legacy_effect_registry.build_registry(object())


@pytest.mark.lock
def test_guarded_platform_effects_forward_to_real_implementation() -> None:
    class Impl:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict]] = []

        def enqueue_evolution_job(self, **kwargs):
            self.calls.append(("enqueue_evolution_job", dict(kwargs)))
            return {"ok": True}

        def suggest_offer_patch(self, **kwargs):
            self.calls.append(("suggest_offer_patch", dict(kwargs)))
            return {"ok": True}

        def apply_offer_patch(self, **kwargs):
            self.calls.append(("apply_offer_patch", dict(kwargs)))
            return {"ok": True}

    impl = Impl()
    guarded = GuardedEffectsPort("platform-token", impl)
    set_effect_capability("platform-token")
    try:
        assert guarded.enqueue_evolution_job(job_kind="audit") == {"ok": True}
        assert guarded.suggest_offer_patch(offer_id="offer-1") == {"ok": True}
        assert guarded.apply_offer_patch(offer_id="offer-1") == {"ok": True}
    finally:
        clear_effect_capability()

    assert [name for name, _ in impl.calls] == [
        "enqueue_evolution_job",
        "suggest_offer_patch",
        "apply_offer_patch",
    ]


@pytest.mark.lock
def test_executor_effects_bundle_carries_canonical_event_store(monkeypatch) -> None:
    class Impl:
        def __init__(self, **kwargs) -> None:
            self.kwargs = dict(kwargs)

    canonical_event_store = object()
    monkeypatch.setattr(executor_state_module, "load_effects_impl", lambda: Impl)
    infra = SimpleNamespace(
        delivery_state=object(),
        decision_ledger=object(),
        payments_outbox=object(),
        telegram_outbound_queue=object(),
        settings_store=object(),
        messaging_policy_store=object(),
        messaging_policy_reader=object(),
        http_transport=object(),
        effect_router=object(),
        event_store=canonical_event_store,
    )

    bundle = executor_state_module.build_executor_effects_bundle(
        event_log=object(),
        policy_registry=object(),
        infra=infra,
    )

    assert bundle.effects.impl.kwargs["event_store"] is canonical_event_store
