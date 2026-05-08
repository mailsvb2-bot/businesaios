from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class SynonymEntity:
    canonical: str
    synonyms: tuple[str, ...]


DECISION_CORE_SYNONYMS: Final[SynonymEntity] = SynonymEntity("DecisionCore", ("brain", "policy_brain", "decision_engine", "decision_engine_facade", "strategy_brain", "second_decision_core", "shadow_decision_core"))
WORLD_STATE_SYNONYMS: Final[SynonymEntity] = SynonymEntity("world_state", ("shadow_state", "shadow_world_model", "parallel_world_model", "duplicate_state", "mirror_world_state", "secondary_world_state"))
EXECUTABLE_ACTION_SYNONYMS: Final[SynonymEntity] = SynonymEntity("executable_action", ("final_action", "selected_action", "best_action", "issued_action", "action_plan"))
THIN_WRAPPER_SYNONYMS: Final[SynonymEntity] = SynonymEntity("thin_wrapper", ("public_api", "compat", "facade", "alias", "bridge", "wrapper"))
REGISTRY: Final[tuple[SynonymEntity, ...]] = (DECISION_CORE_SYNONYMS, WORLD_STATE_SYNONYMS, EXECUTABLE_ACTION_SYNONYMS, THIN_WRAPPER_SYNONYMS)


def iter_synonyms_for(canonical: str) -> tuple[str, ...]:
    lowered = canonical.strip().lower()
    for entity in REGISTRY:
        if entity.canonical.lower() == lowered:
            return entity.synonyms
    return ()


def find_canonical_for(value: str) -> str | None:
    needle = value.strip().lower()
    for entity in REGISTRY:
        if entity.canonical.lower() == needle or needle in {item.lower() for item in entity.synonyms}:
            return entity.canonical
    return None


def is_synonym_of(canonical: str, value: str) -> bool:
    lowered_canonical, lowered_value = canonical.strip().lower(), value.strip().lower()
    return lowered_canonical == lowered_value or lowered_value in {item.lower() for item in iter_synonyms_for(canonical)}


__all__ = ["SynonymEntity", "REGISTRY", "find_canonical_for", "is_synonym_of", "iter_synonyms_for"]
