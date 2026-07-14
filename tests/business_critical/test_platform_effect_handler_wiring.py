from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.actions.catalog import build_catalog
from runtime.boot.actions_registry import INLINE_ALLOWLIST, get_spec
from runtime.boot.handler_groups.ops import register_ops_handlers
from runtime.effects import registry as legacy_effect_registry
from runtime.handlers import ActionHandlerRegistry
from runtime.handlers.platform_effects import handle_apply_offer_patch


PLATFORM_ACTIONS = {
    "enqueue_evolution_job@v1",
    "apply_offer_patch@v1",
    "suggest_offer_patch@v1",
}


class FakePlatformEffects:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def apply_offer_patch(self, **kwargs):
        self.calls.append(dict(kwargs))
        return {"ok": True, "mode": kwargs["mode"]}


def _env() -> SimpleNamespace:
    return SimpleNamespace(
        decision=SimpleNamespace(
            decision_id="decision-platform",
            correlation_id="correlation-platform",
        )
    )


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
def test_legacy_parallel_effect_registry_is_removed_fail_closed() -> None:
    assert legacy_effect_registry.CANON_LEGACY_EFFECT_REGISTRY_REMOVED is True

    with pytest.raises(
        RuntimeError,
        match="LEGACY_EFFECT_ACTION_REGISTRY_REMOVED",
    ):
        legacy_effect_registry.build_registry(object())
