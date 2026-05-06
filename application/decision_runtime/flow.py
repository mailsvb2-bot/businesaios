from __future__ import annotations

from typing import Any

from application.decision_runtime.envelope_builder import bind_product_metadata, build_decision_envelope
from application.decision_state.world_model_metadata import attach_world_model_metadata


def build_payload(*, state, out, pinned_world_model_meta: dict, product_id: str, domain: str, product_version: str):
    tagged = bind_product_metadata(
        payload=dict(out.payload) if isinstance(out.payload, dict) else {},
        product_id=product_id,
        domain=domain,
        product_version=product_version,
    )
    payload = attach_world_model_metadata(envelope_payload=tagged.payload, state=state)
    meta_block = dict(payload.get("meta") or {})
    state_meta = dict(getattr(state, "meta", {}) or {})
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
