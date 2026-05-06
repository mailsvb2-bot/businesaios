from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .canonical_observation import CanonicalObservation


@dataclass(frozen=True)
class ContractDiff:
    equal: bool
    left: CanonicalObservation
    right: CanonicalObservation
    differing_keys: tuple[str, ...]


IGNORED_KEYS = frozenset({"decision_id"})


def compare_contracts(left: Mapping[str, Any] | None, right: Mapping[str, Any] | None) -> ContractDiff:
    left_obs = CanonicalObservation.from_mapping(left)
    right_obs = CanonicalObservation.from_mapping(right)
    keys = sorted((set(left_obs.payload) | set(right_obs.payload)) - IGNORED_KEYS)
    differing = tuple(key for key in keys if left_obs.payload.get(key) != right_obs.payload.get(key))
    return ContractDiff(equal=not differing, left=left_obs, right=right_obs, differing_keys=differing)
