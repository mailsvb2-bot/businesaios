from __future__ import annotations

from pathlib import Path

import pytest

from core.events import event_types
from runtime._internal.effect_types import canonical_effect_action_types
from runtime.boot.actions_registry import all_actions


ROOT = Path(__file__).resolve().parents[2]

PLATFORM_SCOPE_SURFACES = (
    "runtime/boot/actions_catalog.py",
    "runtime/handlers_ops.py",
    "runtime/handler_impl/domains/user_ops.py",
    "runtime/ports/effects_admin.py",
    "runtime/ports/effects_comms.py",
    "runtime/ports/effects_revenue.py",
    "runtime/effects/registry.py",
    "runtime/_internal/effect_types.py",
    "runtime/_internal/effect_payloads.py",
    "runtime/_internal/effect_router.py",
    "runtime/_internal/effects_actions/telegram_actions.py",
    "runtime/_internal/effects_actions/telegram_actions_transport.py",
    "runtime/_internal/effects_actions/telegram/transport.py",
    "core/actions/catalog_groups.py",
    "core/events/event_types.py",
    "core/users/read_model.py",
)

FORBIDDEN_CONSUMER_CAPABILITY_MARKERS = (
    "send_audio@v1",
    "send_audio(",
    "handle_send_audio",
    "TELEGRAM_SEND_AUDIO",
    "telegram.send_audio",
    "audio_sent",
    "audio_started",
    "audio_progress",
    "audio_stopped",
    "audio_completed",
    "log_mood@v1",
    "log_mood(",
    "handle_log_mood",
    "mood_logged",
    "mood_last",
)

FORBIDDEN_GLOBAL_PRICING_STORAGE_MARKERS = (
    "PLANS_PATH",
    "data/plans.json",
    "PRICING_VERSION_OVERRIDE_PATH",
    "pricing_version_override",
    "prepare_plan_price_update",
    "execute_plan_price_update",
)

GHOST_ACTIONS = (
    "reward_observe@v1",
    "growth_propose@v1",
)


def _action_names() -> set[str]:
    return set(all_actions())


@pytest.mark.lock
def test_business_platform_has_no_consumer_audio_or_mood_actions() -> None:
    actions = _action_names()

    assert "send_audio@v1" not in actions
    assert "log_mood@v1" not in actions
    assert all("audio" not in action.casefold() for action in actions)
    assert all("mood" not in action.casefold() for action in actions)


@pytest.mark.lock
def test_unwired_reward_and_growth_ghost_actions_are_not_advertised() -> None:
    actions = _action_names()

    assert all(action not in actions for action in GHOST_ACTIONS)
    assert not (ROOT / "runtime" / "handlers" / "reward_observe.py").exists()
    assert not (ROOT / "runtime" / "handlers" / "growth_propose.py").exists()

    core_boot = (ROOT / "runtime" / "boot" / "handler_groups" / "core.py").read_text(encoding="utf-8")
    public_actions = (ROOT / "runtime" / "actions" / "__init__.py").read_text(encoding="utf-8")
    action_names = (ROOT / "core" / "actions" / "names.py").read_text(encoding="utf-8")
    combined = "\n".join((core_boot, public_actions, action_names))
    for action in GHOST_ACTIONS:
        assert action not in combined
    for marker in ("reward_observer", "growth_proposal_service", "proposal_gateway"):
        assert marker not in core_boot


@pytest.mark.lock
def test_business_platform_effect_router_has_no_audio_effect_type() -> None:
    effect_actions = canonical_effect_action_types()

    assert all("audio" not in action.casefold() for action in effect_actions)


@pytest.mark.lock
def test_business_platform_event_vocabulary_has_no_consumer_mood_audio_events() -> None:
    known = event_types.KNOWN_EVENT_TYPES

    assert all("audio" not in event_type.casefold() for event_type in known)
    assert all("mood" not in event_type.casefold() for event_type in known)


@pytest.mark.lock
def test_canonical_platform_surfaces_do_not_reintroduce_consumer_capabilities() -> None:
    offenders: list[str] = []
    for relative in PLATFORM_SCOPE_SURFACES:
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        for marker in FORBIDDEN_CONSUMER_CAPABILITY_MARKERS:
            if marker in text:
                offenders.append(f"{relative}:{marker}")

    assert offenders == [], "consumer product capabilities leaked into BusinessAIOS platform:\n" + "\n".join(offenders)


@pytest.mark.lock
def test_pricing_runtime_has_no_global_single_product_storage_owner() -> None:
    pricing_surfaces = (
        ROOT / "runtime" / "_internal" / "effects_domains" / "admin_pricing.py",
        ROOT / "runtime" / "_internal" / "effects_domains" / "admin_state_support.py",
    )
    offenders: list[str] = []
    for path in pricing_surfaces:
        text = path.read_text(encoding="utf-8")
        for marker in FORBIDDEN_GLOBAL_PRICING_STORAGE_MARKERS:
            if marker in text:
                offenders.append(f"{path.relative_to(ROOT).as_posix()}:{marker}")

    assert offenders == [], "legacy global pricing storage returned:\n" + "\n".join(offenders)


@pytest.mark.lock
def test_legacy_pricing_sidecar_helper_is_deleted() -> None:
    assert not (
        ROOT / "runtime" / "_internal" / "effects_domains" / "admin_pricing_support.py"
    ).exists()
