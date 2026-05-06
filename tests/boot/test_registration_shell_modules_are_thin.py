from __future__ import annotations

import importlib

WRAPPERS = (
    "catalog",
    "register_action_budget",
    "register_architecture_watch",
    "register_autonomy_advisor",
    "register_creative_intelligence",
    "register_decision_gateway",
    "register_decision_input_service",
    "register_diffusion_watch",
    "register_flow_watch",
    "register_kill_switch",
    "register_market_watch",
    "register_observability",
    "register_reward",
    "register_risk",
    "register_runtime_packet_provider",
    "register_runtime_state_enrichment",
    "register_simulation",
    "register_structure_watch",
    "register_world_state_integration",
)


def test_registration_shell_modules_resolve_to_package_owned_alias_modules() -> None:
    owner = importlib.import_module("boot.registrations")
    for name in WRAPPERS:
        alias = importlib.import_module(f"boot.registrations.{name}")
        if name == "catalog":
            assert getattr(alias, "register_architecture_watch") is getattr(owner, "register_architecture_watch")
        else:
            assert getattr(alias, name) is getattr(owner, name), name
