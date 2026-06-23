from __future__ import annotations


CANON_WORLD_MODEL_BUILDER_FINAL_OWNER = True
CANON_BOOT_WIRING_ONLY = True


from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Optional, Tuple

from runtime.boot import PricingWorldModel, pricing_world_model_from_dict

from runtime.platform.economics.world_model_store_contracts import WorldModelStorePort
from runtime.platform.economics.world_model_store_factory import build_world_model_store
from bootstrap.canonical_decision_world_model import CanonicalDecisionWorldModel
from bootstrap.decision_agi_world_model import DecisionAGIWorldModel
from runtime.boot.env import env_str
from ports.world_model import DecisionWorldModelPort
from bootstrap.pricing_world_model_loader import load_pricing_world_model_for, load_pricing_world_model_with_metadata_for


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


