from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from application.decision_runtime.envelope_builder import bind_product_metadata, build_decision_envelope
from application.decision_state.world_model_metadata import attach_world_model_metadata


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _state_meta(state: Any) -> dict[str, Any]:
    raw = state.get("meta") if isinstance(state, Mapping) else getattr(state, "meta", {})
    return _mapping(raw)


def _canonical_goal_identity(state: Any) -> str | None:
    state_meta = _state_meta(state)
    requested_goal_id = str(state_meta.get("goal_id") or "").strip()
    canonical_context = _mapping(state_meta.get("canonical_goal"))
    canonical_goal = _mapping(canonical_context.get("goal"))
    canonical_goal_id = str(canonical_goal.get("goal_id") or "").strip()
    if requested_goal_id and canonical_goal_id and requested_goal_id != canonical_goal_id:
        raise RuntimeError("DECISION_GOAL_ID_MISMATCH")
    resolved = canonical_goal_id or requested_goal_id
    return resolved or None


def build_payload(
    *,
    state,
    out,
    pinned_world_model_meta: dict,
    tenant_id: str | None,
    product_id: str | None,
    domain: str | None,
    product_version: str | None,
    actor_id: str | None = None,
):
    tagged = bind_product_metadata(
        payload=dict(out.payload) if isinstance(out.payload, dict) else {},
        tenant_id=tenant_id,
        product_id=product_id,
        domain=domain,
        product_version=product_version,
        actor_id=actor_id,
    )
    payload = attach_world_model_metadata(envelope_payload=tagged.payload, state=state)
    meta_block = dict(payload.get("meta") or {})
    state_meta = _state_meta(state)
    canonical_goal_id = _canonical_goal_identity(state)
    if canonical_goal_id:
        payload_goal_id = str(payload.get("goal_id") or "").strip()
        if payload_goal_id and payload_goal_id != canonical_goal_id:
            raise RuntimeError("DECISION_GOAL_ID_MISMATCH")
        meta_goal_id = str(meta_block.get("canonical_goal_id") or "").strip()
        if meta_goal_id and meta_goal_id != canonical_goal_id:
            raise RuntimeError("DECISION_GOAL_ID_MISMATCH")
        payload["goal_id"] = canonical_goal_id
        meta_block["canonical_goal_id"] = canonical_goal_id
    if pinned_world_model_meta:
        meta_block["world_model_meta"] = dict(pinned_world_model_meta)
    if "world_model_explainability" in state_meta:
        meta_block["world_model_explainability"] = state_meta["world_model_explainability"]
    if "constraint_explainability" in state_meta:
        meta_block["constraint_explainability"] = state_meta["constraint_explainability"]
    if meta_block:
        payload["meta"] = meta_block
    return tagged, payload


def build_envelope(*, state, out, payload: dict, policy_id: str, keyring, issuer_id: str, ttl_ms: int, action_schema_version: int, envelope_version: int):
    return build_decision_envelope(
        state=state,
        action=out.action,
        payload=payload,
        policy_id=policy_id,
        keyring=keyring,
        issuer_id=issuer_id,
        ttl_ms=ttl_ms,
        action_schema_version=int(action_schema_version),
        envelope_version=int(envelope_version),
    )


def build_archive_envelope(*, archive_envelope, built, state, pinned_world_model_meta: dict, logger) -> Any:
    # Archive must keep the exact signed envelope bytes.
    # Any payload mutation here would invalidate replay signature checks.
    return archive_envelope
