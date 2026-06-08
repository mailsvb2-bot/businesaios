from __future__ import annotations

import hashlib
import json
from typing import Any, Optional
from collections.abc import Mapping


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def stable_payload_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(_jsonable(dict(payload)), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def extract_world_model_metadata(*, state: Any) -> dict[str, Any]:
    meta = getattr(state, "meta", None)
    meta = dict(meta) if isinstance(meta, dict) else {}

    economy = getattr(state, "economy", None)
    economy = dict(economy) if isinstance(economy, dict) else {}

    out: dict[str, Any] = {}

    world_model_name = meta.get("world_model")
    world_model_kind = meta.get("world_model_kind")
    pricing_model_name = meta.get("pricing_world_model")
    pricing_model_version = meta.get("pricing_world_model_version")
    pricing_model_hash = meta.get("pricing_world_model_hash")
    pricing_model_source = economy.get("world_model_source")

    if world_model_name is not None:
        out["world_model"] = str(world_model_name)
    if world_model_kind is not None:
        out["world_model_kind"] = str(world_model_kind)
    if pricing_model_name is not None:
        out["pricing_world_model"] = str(pricing_model_name)
    if pricing_model_version is not None:
        out["pricing_world_model_version"] = str(pricing_model_version)
    if pricing_model_hash is not None:
        out["pricing_world_model_hash"] = str(pricing_model_hash)
    if pricing_model_source is not None:
        out["world_model_source"] = str(pricing_model_source)

    pricing_state = economy.get("pricing_world_state")
    if isinstance(pricing_state, dict) and pricing_state:
        out["pricing_world_state_hash"] = stable_payload_hash(pricing_state)

    return out


def attach_world_model_metadata(
    *,
    envelope_payload: dict[str, Any],
    state: Any,
) -> dict[str, Any]:
    meta = dict(envelope_payload or {})
    wm = extract_world_model_metadata(state=state)
    if wm:
        meta["world_model_meta"] = wm
    return meta


def summarize_pricing_world_state(*, state: Any) -> dict[str, Any] | None:
    economy = getattr(state, "economy", None)
    economy = dict(economy) if isinstance(economy, dict) else {}
    ws = economy.get("pricing_world_state")
    if not isinstance(ws, dict) or not ws:
        return None

    out: dict[str, Any] = {}

    for key in (
        "expected_profit",
        "expected_revenue",
        "conversion_prob_at_price",
        "point_elasticity",
        "current_price",
        "marginal_cost",
    ):
        value = ws.get(key)
        if isinstance(value, (int, float, str, bool)) or value is None:
            out[key] = value

    if not out:
        return None
    return out


def extract_pinned_world_model_meta_from_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(payload or {})

    wm = payload.get("world_model_meta")
    if isinstance(wm, dict):
        return dict(wm)

    meta = payload.get("meta")
    if isinstance(meta, dict):
        nested = meta.get("world_model_meta")
        if isinstance(nested, dict):
            return dict(nested)

    return {}
