from __future__ import annotations

import logging
from collections.abc import Mapping
from threading import Lock, Thread
from typing import Any

from application.decision_policy.pricing import allowed_price_band, band_rank, merge_price_constraints
from application.decision_runtime.run import run_decision
from contracts.action_intent import ActionIntentV1
from contracts.executable_action import ExecutableAction
from core.decision_core_contract import CANONICAL_DECISION_CORE_IMPORT_PATH
from core.utils.canonical import payload_hash as canonical_payload_hash
from kernel.decision_signer import DecisionSigner
from ports.world_model import DecisionWorldModelPort

logger = logging.getLogger(__name__)
ENVELOPE_VERSION = 1
SOVEREIGN_DECISION_CORE = True
CANON_EXECUTABLE_ACTION_PROJECTION_OWNER = True
CANON_SHADOW_OBSERVATION_OWNER = True


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



def project_action_intent(
    *, decision_id: str, correlation_id: str, decided_action_type: str, channel: str,
    tenant_id: str, business_id: str, payload: Mapping[str, Any], requested_by: str = "decision_core",
) -> ActionIntentV1:
    """Project a signed sovereign decision into the canonical non-effectful intent contract."""

    normalized_decision_id = str(decision_id or "").strip()
    return ActionIntentV1.from_projection(
        intent_id=f"intent:{normalized_decision_id}", tenant_id=str(tenant_id or "").strip(),
        business_id=str(business_id or "").strip(), decision_id=normalized_decision_id,
        correlation_id=str(correlation_id or "").strip(), action_type=str(decided_action_type or "").strip(),
        channel=str(channel or "").strip(), payload=payload, payload_hash=canonical_payload_hash(dict(payload)),
        requested_by=str(requested_by or "decision_core").strip(),
    )

def project_executable_action(
    *,
    decision_id: str,
    correlation_id: str,
    decided_action_type: str,
    channel: str,
    payload: Mapping[str, Any],
    capability_plan: Any,
    enforce_capability_plan: bool,
    action_intent: ActionIntentV1 | None = None,
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

    if action_intent is not None:
        if action_intent.decision_id != normalized_decision_id or action_intent.correlation_id != normalized_correlation_id:
            raise ValueError("action intent identity does not match executable projection")
        if action_intent.action_type != normalized_action_type or action_intent.channel != normalized_channel:
            raise ValueError("action intent action/channel does not match executable projection")
        if canonical_payload_hash(dict(action_intent.payload)) != action_intent.payload_hash:
            raise ValueError("action intent payload integrity check failed")
        if dict(action_intent.payload) != dict(payload):
            raise ValueError("action intent payload does not match executable projection")
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
        intent_id="" if action_intent is None else action_intent.intent_id,
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
        shadow_observer=None,
    ):
        self._selector = selector
        self._keyring = keyring
        self._schemas = schema_registry
        self._snapshots = snapshot_store
        self._events = event_log
        self._archive = decision_archive
        self._ttl_ms = int(ttl_ms)
        self._issuer_id = str(issuer_id or "businesaios-core").strip() or "businesaios-core"
        self._shadow_observer = shadow_observer
        self._shadow_busy = Lock()

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

    def observe_shadow(self, *, state, production_envelope, production_policy_id: str):
        candidate = None if self._shadow_observer is None else self._selector.resolve_shadow_policy(state, production_policy_id=str(production_policy_id))
        return None if candidate is None else self._shadow_observer.observe(state=state, production_envelope=production_envelope, candidate_policy=candidate)

    def dispatch_shadow(self, **observation) -> bool:
        if self._shadow_observer is None or not self._shadow_busy.acquire(blocking=False): return False
        def run() -> None:
            try: self.observe_shadow(**observation)
            except Exception: pass
            finally: self._shadow_busy.release()
        Thread(target=run, name="decision-shadow-observer", daemon=True).start(); return True

    def shadow_rollout_status(self, candidate_policy_id: str) -> dict[str, bool]:
        from core.policies.staged_rollout import RolloutGuard
        registered = self._selector.is_registered_shadow_candidate(str(candidate_policy_id)); metrics = self._shadow_observer.metrics(str(candidate_policy_id)) if registered and self._shadow_observer is not None else {}
        return {"registered": registered, "promotable": bool(registered and RolloutGuard.allow_promotion(metrics))}

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
    "project_action_intent",
    "project_executable_action",
]
