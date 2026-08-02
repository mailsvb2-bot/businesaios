"""Decision-core support helpers extracted from boot_core_assembly."""

from __future__ import annotations

from typing import Any

from bootstrap.world_model_boot_check import build_and_verify_default_world_model
from config.live_canary_policy import DEFAULT_LIVE_CANARY_POLICY
from core.ai import set_decision_core_singleton
from core.ai.decision_core import DecisionCore
from core.policies.shadow import ShadowDecisionLedger, ShadowEvaluator
from runtime.experiments.wiring import (
    attach_live_canary,
    start_live_canary_runtime,
)

CANON_BOOT_WIRING_ONLY = True
CANON_BOOT_REGISTERS_DECISION_CORE_SINGLETON = True


def build_world_model(*, event_log: Any) -> object:
    return build_and_verify_default_world_model(event_log=event_log)


def _attach_configured_live_canary(core: DecisionCore, policy_selector: Any) -> None:
    policy = DEFAULT_LIVE_CANARY_POLICY
    if not policy.enabled:
        return
    policy.assert_valid()
    registry = getattr(policy_selector, "_registry", None)
    rollout_config = getattr(registry, "rollout_config", None)
    if not callable(rollout_config):
        raise RuntimeError("LIVE_CANARY_POLICY_REGISTRY_REQUIRED")
    candidate_policy_id, _rollout_pct = rollout_config()
    candidate = str(candidate_policy_id or "").strip()
    if not candidate:
        raise RuntimeError("LIVE_CANARY_CANDIDATE_REQUIRED")
    attach_live_canary(
        core,
        policy_registry=registry,
        candidate_policy_id=candidate,
        policy=policy,
    )
    start_live_canary_runtime(core)


def build_decision_core(
    *,
    policy_selector: Any,
    keyring: Any,
    schemas: Any,
    snapshot_store: Any,
    event_log: Any,
    decision_archive: Any,
    issuer_id: str,
):
    """Construct and register the only process-wide DecisionCore."""

    world_model = build_world_model(event_log=event_log)
    core = DecisionCore(
        selector=policy_selector,
        keyring=keyring,
        schema_registry=schemas,
        snapshot_store=snapshot_store,
        event_log=event_log,
        decision_archive=decision_archive,
        world_model=world_model,
        issuer_id=issuer_id,
        shadow_observer=ShadowEvaluator(ShadowDecisionLedger(event_log), schemas),
    )
    _attach_configured_live_canary(core, policy_selector)
    set_decision_core_singleton(core)
    return world_model, core


__all__ = [
    "CANON_BOOT_WIRING_ONLY",
    "CANON_BOOT_REGISTERS_DECISION_CORE_SINGLETON",
    "build_world_model",
    "build_decision_core",
]
