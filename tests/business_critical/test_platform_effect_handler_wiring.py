from __future__ import annotations

import pytest

from runtime.boot.actions_registry import INLINE_ALLOWLIST, get_spec
from runtime.boot.handler_groups.ops import register_ops_handlers
from runtime.effects import registry as legacy_effect_registry
from runtime.handlers import ActionHandlerRegistry


PLATFORM_ACTIONS = {
    "enqueue_evolution_job@v1",
    "apply_offer_patch@v1",
    "suggest_offer_patch@v1",
}


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
def test_legacy_parallel_effect_registry_is_removed_fail_closed() -> None:
    assert legacy_effect_registry.CANON_LEGACY_EFFECT_REGISTRY_REMOVED is True

    with pytest.raises(
        RuntimeError,
        match="LEGACY_EFFECT_ACTION_REGISTRY_REMOVED",
    ):
        legacy_effect_registry.build_registry(object())
