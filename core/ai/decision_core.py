from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from application.decision_policy.pricing import allowed_price_band, band_rank, merge_price_constraints
from application.decision_runtime.run import run_decision
from contracts.executable_action import ExecutableAction
from core.decision_core_contract import CANONICAL_DECISION_CORE_IMPORT_PATH
from kernel.decision_signer import DecisionSigner
from ports.world_model import DecisionWorldModelPort

logger = logging.getLogger(__name__)
ENVELOPE_VERSION = 1
SOVEREIGN_DECISION_CORE = True
CANON_EXECUTABLE_ACTION_PROJECTION_OWNER = True


def _sign_payload(payload: dict, *, secret: bytes) -> str:
    return DecisionSigner.sign(payload=payload, secret=secret)


def _non_effectful_capability_patch(payload_patch: Mapping[str, Any]) -> dict[str, Any]:
    preserved_keys = {
        "capability_diagnostics",
        "execution_verdict",
        "policy_verdict",
        "routing_explanation",
        "capability_fallback_kind",
        "capability_fallback_reason",
        "capability_fallback_from",
    }
    return {key: value for key, value in payload_patch.items() if key in preserved_keys}


def project_executable_action(
    *,
    decision_id: str,
    correlation_id: str,
    decided_action_type: str,
    channel: str,
    payload: Mapping[str, Any],
    capability_plan: Any,
    enforce_capability_plan: bool,
) -> ExecutableAction:
    """Project the signed decision into the sole executable-action contract.

    Capability planning may constrain an already-issued decision, but the final
    executable action type is selected and constructed only inside the sovereign
    decision-core module. No application step may mint an independent action.
    """

    normalized_decision_id = str(decision_id or "").strip()
    normalized_correlation_id = str(correlation_id or "").strip()
    normalized_action_type = str(decided_action_type or "").strip()
    normalized_channel = str(channel or "").strip()
    if not normalized_decision_id:
        raise ValueError("decision_id is required")
    if not normalized_correlation_id:
        raise ValueError("correlation_id is required")
    if not normalized_action_type:
        raise ValueError("decided_action_type is required")
    if not normalized_channel:
        raise ValueError("channel is required")

    projected_payload = dict(payload)
    projected_payload["capability_planning"] = capability_plan.to_dict()
    payload_patch = dict(capability_plan.payload_patch)
    action_type = normalized_action_type
    if bool(enforce_capability_plan) or not bool(capability_plan.allowed):
        projected_payload.update(payload_patch)
        if bool(capability_plan.allowed):
            action_type = str(capability_plan.action_type or normalized_action_type)
        else:
            projected_payload.setdefault("operator_required", True)
            projected_payload.setdefault("status", "capability_preflight_blocked")
            projected_payload.setdefault("capability_blocked", True)
            action_type = "notify_owner"
    else:
        projected_payload.update(_non_effectful_capability_patch(payload_patch))
        if bool(capability_plan.fallback_used):
            proposed = str(capability_plan.action_type or normalized_action_type).strip()
            if proposed:
                action_type = proposed

    action = ExecutableAction(
        action_id=f"action:{normalized_decision_id}",
        action_type=action_type,
        channel=normalized_channel,
        payload=projected_payload,
        decision_id=normalized_decision_id,
        correlation_id=normalized_correlation_id,
        objective_name="profit_adjusted_growth",
    )
    issues = action.validate_contract()
    if issues:
        raise ValueError(f"invalid executable action projection: {','.join(issues)}")
    return action


class DecisionCore:
    """The ONLY decision issuance point.
    Contract:
      decide(WorldState) -> DecisionEnvelope
    Invariants:
      - no side-effects
      - always emits proof event decision_issued
    """

    CANONICAL_IMPORT_PATH = CANONICAL_DECISION_CORE_IMPORT_PATH
    IS_SOVEREIGN_DECISION_CORE = True

    def __init__(
        self,
        selector,
        keyring,
        schema_registry,
        snapshot_store,
        event_log,
        decision_archive=None,
        ttl_ms: int = 5 * 60 * 1000,
        world_model: DecisionWorldModelPort | None = None,
        issuer_id: str = "businesaios-core",
    ):
        self._selector = selector
        self._keyring = keyring
        self._schemas = schema_registry
        self._snapshots = snapshot_store
        self._events = event_log
        self._archive = decision_archive
        self._ttl_ms = int(ttl_ms)
        self._issuer_id = str(issuer_id or "businesaios-core").strip() or "businesaios-core"

        if world_model is not None and not isinstance(world_model, DecisionWorldModelPort):
            raise TypeError(
                "DecisionCore.world_model must implement DecisionWorldModelPort "
                "(canonical enrich_state contract)"
            )
        self._world_model: DecisionWorldModelPort | None = world_model

    @staticmethod
    def _band_rank(band: str | None) -> int:
        return band_rank(band)

    def _allowed_price_band(self, state) -> str:
        """Compatibility shim for older callers/tests.

        The canonical implementation lives in core.ai.decision_pricing.allowed_price_band.
        DecisionCore delegates there and keeps no second pricing brain.
        """
        return allowed_price_band(state=state, logger=logger)

    def _merge_price_constraints(self, *, base: dict | None, override: dict | None) -> dict:
        """Compatibility shim for conservative band merging.

        Canonical implementation lives in core.ai.decision_pricing.merge_price_constraints.
        """
        return merge_price_constraints(base=base, override=override, logger=logger)

    def decide(self, state):
        return run_decision(core=self, state=state, envelope_version=ENVELOPE_VERSION, logger=logger)

    def optimize(self, state):
        """Canonical alias used by runtime and tests. Still routes to the single decision issuer."""
        return self.decide(state)

    def issue(self, state):
        """Compatibility alias for orchestrators. No alternate brain is introduced."""
        return self.optimize(state)


__all__ = [
    "CANON_EXECUTABLE_ACTION_PROJECTION_OWNER",
    "DecisionCore",
    "ENVELOPE_VERSION",
    "SOVEREIGN_DECISION_CORE",
    "project_executable_action",
]
