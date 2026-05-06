from __future__ import annotations


CANON_WORLD_MODEL_BUILDER_FINAL_OWNER = True
CANON_BOOT_WIRING_ONLY = True


from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Optional, Tuple

from runtime.boot import PricingWorldModel, pricing_world_model_from_dict

from runtime.platform.economics.world_model_store import WorldModelStorePort, build_world_model_store
from bootstrap.canonical_decision_world_model import CanonicalDecisionWorldModel
from bootstrap.decision_agi_world_model import DecisionAGIWorldModel
from runtime.boot.env import env_str
from ports.world_model import DecisionWorldModelPort


def build_default_world_model(
    *,
    store: Optional[WorldModelStorePort] = None,
) -> DecisionWorldModelPort:
    kind = env_str("WORLD_MODEL_KIND", "hybrid@v1").strip().lower()
    if kind in {"decision_agi@v1", "agi@v1", "agi", "decision_agi"}:
        base_kind = env_str("DECISION_AGI_BASE_WORLD_MODEL_KIND", "hybrid@v1").strip().lower() or "hybrid@v1"
        model: DecisionWorldModelPort = DecisionAGIWorldModel(
            store=store,
            kind=kind,
            base_kind=base_kind,
        )
    else:
        model = CanonicalDecisionWorldModel(store=store, kind=kind)
    _validate_decision_world_model(model)
    return model


def describe_default_world_model() -> Dict[str, Any]:
    kind = env_str("WORLD_MODEL_KIND", "hybrid@v1").strip().lower()
    if kind in {"decision_agi@v1", "agi@v1", "agi", "decision_agi"}:
        base_kind = env_str("DECISION_AGI_BASE_WORLD_MODEL_KIND", "hybrid@v1").strip().lower() or "hybrid@v1"
        return {
            "builder": "bootstrap.world_model_builder.build_default_world_model",
            "implementation": "bootstrap.decision_agi_world_model.DecisionAGIWorldModel",
            "kind": kind,
            "base_kind": base_kind,
        }
    return {
        "builder": "bootstrap.world_model_builder.build_default_world_model",
        "implementation": "bootstrap.canonical_decision_world_model.CanonicalDecisionWorldModel",
        "kind": kind,
    }


def _validate_decision_world_model(model: Any) -> None:
    enrich = getattr(model, "enrich_state", None)
    if not callable(enrich):
        raise TypeError("decision world model must provide callable enrich_state(state)")


def load_pricing_world_model_for(
    *,
    tenant_id: str,
    product_id: str,
    store: Optional[WorldModelStorePort] = None,
) -> PricingWorldModel:
    model, _ = load_pricing_world_model_with_metadata_for(
        tenant_id=tenant_id,
        product_id=product_id,
        store=store,
    )
    return model


def load_pricing_world_model_with_metadata_for(
    *,
    tenant_id: str,
    product_id: str,
    store: Optional[WorldModelStorePort] = None,
) -> Tuple[PricingWorldModel, Dict[str, Any]]:
    store = store or build_world_model_store()
    payload: Optional[Dict[str, Any]] = store.get_active_payload(
        tenant_id=str(tenant_id),
        product_id=str(product_id),
    )

    if not payload:
        return PricingWorldModel.default(), {
            "pricing_world_model": "default_pricing_world_model@v1",
            "pricing_world_model_version": "default",
            "pricing_world_model_hash": "default",
            "pricing_world_model_origin": "default_fallback",
        }

    try:
        model = pricing_world_model_from_dict(payload)
        version = payload.get("version") or payload.get("schema_version") or payload.get("kind") or "unknown"
        model_id = payload.get("model_id") or payload.get("id") or payload.get("name") or "store_payload"
        model_hash = _stable_payload_hash(payload)
        return model, {
            "pricing_world_model": str(model_id),
            "pricing_world_model_version": str(version),
            "pricing_world_model_hash": str(model_hash),
            "pricing_world_model_origin": "store",
        }
    except Exception:
        return PricingWorldModel.default(), {
            "pricing_world_model": "default_pricing_world_model@v1",
            "pricing_world_model_version": "default_after_deserialize_error",
            "pricing_world_model_hash": "default_after_deserialize_error",
            "pricing_world_model_origin": "default_fallback_after_error",
        }


def _stable_payload_hash(payload: Dict[str, Any]) -> str:
    import hashlib
    import json

    def _jsonable(value: Any) -> Any:
        if isinstance(value, dict):
            return {str(k): _jsonable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [_jsonable(v) for v in value]
        if is_dataclass(value):
            return _jsonable(asdict(value))
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)

    encoded = json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
