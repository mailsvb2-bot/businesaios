from __future__ import annotations

CANON_BOOT_WIRING_ONLY = True

"""Decision-core support helpers extracted from boot_core_assembly."""

from typing import Any

from bootstrap.world_model_boot_check import build_and_verify_default_world_model
from core.ai.decision_core import DecisionCore


def build_world_model(*, event_log: Any) -> object:
    return build_and_verify_default_world_model(event_log=event_log)


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
    """Keep DecisionCore construction local to the canonical boot path."""
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
    )
    return world_model, core


__all__ = ["CANON_BOOT_WIRING_ONLY", "build_world_model", "build_decision_core"]
