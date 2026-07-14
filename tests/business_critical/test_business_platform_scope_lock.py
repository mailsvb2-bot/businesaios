from __future__ import annotations

from pathlib import Path

import pytest

from core.events import event_types
from runtime._internal.effect_types import canonical_effect_action_types
from runtime.boot.actions_registry import all_actions
from runtime.messaging.channel_types import ALL_CHANNELS


ROOT = Path(__file__).resolve().parents[2]

PRESERVED_USER_ACTIONS = {
    "send_audio@v1",
    "log_mood@v1",
    "reward_observe@v1",
    "growth_propose@v1",
}

PRESERVED_MULTI_MESSENGER_CHANNELS = {
    "telegram",
    "whatsapp",
    "sms",
    "email",
    "messenger",
    "instagram",
    "web_chat",
    "api",
}

PRESERVED_USER_EVENTS = {
    "audio_sent",
    "audio_started",
    "audio_progress",
    "audio_stopped",
    "audio_completed",
    "mood_logged",
    "gift_token_created",
    "gift_redeemed",
    "gift_redeem_failed",
}

FORBIDDEN_GLOBAL_PRICING_STORAGE_MARKERS = (
    "PLANS_PATH",
    "data/plans.json",
    "PRICING_VERSION_OVERRIDE_PATH",
    "pricing_version_override",
    "prepare_plan_price_update",
    "execute_plan_price_update",
)


@pytest.mark.lock
def test_complete_user_action_surface_is_preserved_in_canonical_registry() -> None:
    assert PRESERVED_USER_ACTIONS.issubset(set(all_actions()))


@pytest.mark.lock
def test_reward_and_growth_compatibility_routes_are_canonically_wired() -> None:
    core_boot = (
        ROOT / "runtime" / "boot" / "handler_groups" / "core.py"
    ).read_text(encoding="utf-8")
    assert (
        ROOT / "runtime" / "handlers" / "reward_observe.py"
    ).exists()
    assert (
        ROOT / "runtime" / "handlers" / "growth_propose.py"
    ).exists()
    for marker in (
        "reward_observe@v1",
        "growth_propose@v1",
        "reward_observer",
        "growth_proposal_service",
        "proposal_gateway",
    ):
        assert marker in core_boot


@pytest.mark.lock
def test_audio_transport_remains_an_executor_owned_adapter() -> None:
    assert "telegram.send_audio" in canonical_effect_action_types()

    legacy_registry = (
        ROOT / "runtime" / "effects" / "registry.py"
    ).read_text(encoding="utf-8")
    assert "CANON_LEGACY_EFFECT_REGISTRY_REMOVED = True" in legacy_registry
    for action in PRESERVED_USER_ACTIONS:
        assert f'"{action}":' not in legacy_registry


@pytest.mark.lock
def test_preserved_user_events_are_in_the_strict_vocabulary() -> None:
    assert PRESERVED_USER_EVENTS.issubset(event_types.KNOWN_EVENT_TYPES)


@pytest.mark.lock
def test_user_functionality_restoration_does_not_narrow_multimessenger_surface() -> None:
    assert PRESERVED_MULTI_MESSENGER_CHANNELS.issubset(set(ALL_CHANNELS))


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
                offenders.append(
                    f"{path.relative_to(ROOT).as_posix()}:{marker}"
                )

    assert offenders == [], "legacy global pricing storage returned:\n" + "\n".join(offenders)


@pytest.mark.lock
def test_legacy_pricing_sidecar_helper_is_deleted() -> None:
    assert not (
        ROOT
        / "runtime"
        / "_internal"
        / "effects_domains"
        / "admin_pricing_support.py"
    ).exists()
