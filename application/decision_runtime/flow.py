from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any

from application.decision_runtime.envelope_builder import bind_product_metadata, build_decision_envelope
from application.decision_state.world_model_metadata import attach_world_model_metadata
from contracts.messaging_channels import ALL_CHANNELS
from core.ai.action_ranking import OBJECTIVE_DIMENSIONS


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
    return requested_goal_id or None


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _world_model_meta_from_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    return _mapping(payload.get("world_model_meta")) or _mapping(
        _mapping(payload.get("meta")).get("world_model_meta")
    )


def _decision_contract_v2_seed(
    *,
    state: Any,
    out: Any,
    payload: Mapping[str, Any],
    policy_id: str,
) -> dict[str, Any]:
    state_meta = _state_meta(state)
    ranking = _mapping(getattr(out, "ranking", {}) or {})
    decision_context = _mapping(getattr(out, "_decision_context", {}) or {})
    alternatives_raw = decision_context.get("alternatives", ranking.get("_decision_alternatives"))
    alternatives = (
        tuple(dict(item) for item in alternatives_raw if isinstance(item, Mapping))
        if isinstance(alternatives_raw, list | tuple)
        else None
    )
    selection = _mapping(decision_context.get("selection", ranking.get("_decision_selection"))) or {
        "option_id": str(getattr(out, "action", "") or "")
    }

    world_model_meta = _world_model_meta_from_payload(payload)
    confidence = _finite_number(payload.get("confidence"))
    expected_value = _finite_number(payload.get("expected_value"))
    objective_projection = {
        dimension: _finite_number(ranking.get(f"objective:{dimension}"))
        for dimension in OBJECTIVE_DIMENSIONS
    }
    if any(value is None for value in objective_projection.values()):
        objective_projection = None
    risk: Any = payload.get("risk") if "risk" in payload else None
    if risk is None:
        risk_penalty = _finite_number(ranking.get("risk_penalty"))
        if risk_penalty is not None:
            risk = {"risk_penalty": risk_penalty}

    baseline = state_meta.get("do_nothing_baseline")
    uncertainties = [
        f"{name}:UNKNOWN" for name, value in (
            ("alternatives", alternatives), ("confidence", confidence),
            ("expected_value", expected_value), ("objective_vector", objective_projection),
            ("risk", risk), ("do_nothing_baseline", baseline),
        ) if value is None
    ]

    product = _mapping(state.get("product") if isinstance(state, Mapping) else getattr(state, "product", {}))
    business_id = str(
        payload.get("business_id") or product.get("business_id") or state_meta.get("business_id") or "UNKNOWN"
    ).strip() or "UNKNOWN"
    goal_id = str(payload.get("goal_id") or _mapping(payload.get("meta")).get("canonical_goal_id") or "").strip() or None
    model_profile_raw = state_meta.get("model_profile")
    model_profile = model_profile_raw.strip() if isinstance(model_profile_raw, str) and model_profile_raw.strip() else "UNKNOWN"
    canonical_goal_context = _mapping(state_meta.get("canonical_goal"))
    canonical_goal = _mapping(canonical_goal_context.get("goal"))
    constraint_view: Any = state_meta.get("constraint_explainability")
    if constraint_view is None:
        constraint_view = canonical_goal_context.get("constraints")
    deadline = canonical_goal.get("deadline_at_ms")

    return {
        "business_id": business_id,
        "goal_id": goal_id,
        "world_state_version": str(world_model_meta.get("semantic_state_id") or "UNKNOWN"),
        "agent_id": "PENDING_ISSUER_BINDING",
        "model_profile": model_profile,
        "decision_strategy": str(policy_id or "UNKNOWN"),
        "alternatives": alternatives,
        "selected_option": selection,
        "rationale": {
            "evidence": list(world_model_meta.get("evidence_refs") or ()),
            "constraints": constraint_view,
            "alternatives": (
                None
                if alternatives is None
                else [str(item.get("option_id") or "") for item in alternatives]
            ),
            "selection_reason": str(selection.get("reason") or "UNKNOWN"),
            "uncertainties": uncertainties,
            "expected_outcome": payload.get("expected_outcome"),
            "risk": risk,
            "objective_projection": objective_projection,
        },
        "confidence": confidence,
        "expected_value": expected_value,
        "risk": risk,
        "created_at": 0,
        "do_nothing_baseline": baseline,
        "deadline": deadline,
    }


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
    meta_block.pop("inbound_user_reply", None)
    if "meta" in payload:
        payload["meta"] = meta_block
    state_meta = _state_meta(state)
    session = _mapping(state.get("session") if isinstance(state, Mapping) else getattr(state, "session", {}))
    channel = str(session.get("channel") or "").strip().lower()
    event_id = session.get("messaging_update_id") if channel == "telegram" else session.get("transport_message_id")
    valid_event = (type(event_id) is int and event_id >= 0) if channel == "telegram" else (
        isinstance(event_id, str) and bool(event_id.strip()) and len(event_id) <= 256
    )
    state_user = str((state.get("user_id") if isinstance(state, Mapping) else getattr(state, "user_id", "")) or "")
    state_tenant = str((state.get("tenant_id") if isinstance(state, Mapping) else getattr(state, "tenant_id", "")) or "")
    tenant_matches = bool(state_tenant and str(payload.get("tenant_id") or "") == state_tenant)
    if (getattr(out, "action", "") == "send_message@v1"
            and session.get("source") in {"messaging", "customer_bot"}
            and channel in ALL_CHANNELS and valid_event
            and tenant_matches
            and state_user and str(payload.get("user_id") or "") == state_user
            and str(payload.get("channel") or channel).strip().lower() == channel
            and (not session.get("chat_id") or str(payload.get("chat_id") or "") == str(session["chat_id"]))
            and payload.get("recipient_count") in (None, 1)):
        meta_block["inbound_user_reply"] = {
            "channel": channel, "update_id": event_id,
            "tenant_id": state_tenant, "user_id": state_user,
            **({"chat_id": str(session["chat_id"])} if session.get("chat_id") else {}),
        }
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
        product = _mapping(
            state.get("product") if isinstance(state, Mapping) else getattr(state, "product", {})
        )
        canonical_business_id = str(
            product.get("business_id") or state_meta.get("business_id") or ""
        ).strip()
        if canonical_business_id:
            payload_business_id = str(payload.get("business_id") or "").strip()
            if payload_business_id and payload_business_id != canonical_business_id:
                raise RuntimeError("DECISION_BUSINESS_ID_MISMATCH")
            payload["business_id"] = canonical_business_id
        requested_autonomy = str(state_meta.get("autonomy_tier") or "").strip()
        if requested_autonomy:
            payload["autonomy_tier"] = requested_autonomy
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
    contract_v2 = (
        None
        if int(envelope_version) < 2
        else _decision_contract_v2_seed(
            state=state,
            out=out,
            payload=payload,
            policy_id=policy_id,
        )
    )
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
        decision_contract_v2=contract_v2,
    )


def build_archive_envelope(*, archive_envelope, built, state, pinned_world_model_meta: dict, logger) -> Any:
    # Archive must keep the exact signed envelope bytes.
    # Any payload mutation here would invalidate replay signature checks.
    return archive_envelope
