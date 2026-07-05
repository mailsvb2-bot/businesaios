"""Lightweight decision-state package surface."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_CANONICAL_EXPORTS: dict[str, tuple[str, str]] = {
    'apply_causal_constraints': ('application.decision_state.state_constraints', 'apply_causal_constraints'),
    'apply_price_constraints': ('application.decision_state.state_constraints', 'apply_price_constraints'),
    'pricing_constraints_from_state': ('application.decision_state.state_constraints', 'pricing_constraints_from_state'),
    'enrich_state_with_world_model': ('application.decision_state.state_enrichment', 'enrich_state_with_world_model'),
    'extract_product_metadata': ('application.decision_state.state_enrichment', 'extract_product_metadata'),
    'attach_world_model_explainability': ('application.decision_state.state_world_model_enricher', 'attach_world_model_explainability'),
    'attach_world_model_metadata': ('application.decision_state.world_model_metadata', 'attach_world_model_metadata'),
    'extract_pinned_world_model_meta_from_payload': ('application.decision_state.world_model_metadata', 'extract_pinned_world_model_meta_from_payload'),
    'extract_world_model_metadata': ('application.decision_state.world_model_metadata', 'extract_world_model_metadata'),
    'stable_payload_hash': ('application.decision_state.world_model_metadata', 'stable_payload_hash'),
    'summarize_pricing_world_state': ('application.decision_state.world_model_metadata', 'summarize_pricing_world_state'),
    'replay_state_against_world_model': ('application.decision_state.world_model_replay', 'replay_state_against_world_model'),
}


def __getattr__(name: str) -> Any:
    try:
        module_name, attr_name = _CANONICAL_EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(import_module(module_name), attr_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_CANONICAL_EXPORTS))


__all__ = sorted(_CANONICAL_EXPORTS)
