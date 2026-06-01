from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

CANON_POLICY_SEMANTICS_GUARD = True


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class UnifiedPolicySemantics:
    autonomy_tier: str
    capability_policy: Mapping[str, Any]
    planning_policy: Mapping[str, Any]
    approval_policy: Mapping[str, Any]


class PolicySemanticsGuard:
    def normalize(self, payload: Mapping[str, Any]) -> UnifiedPolicySemantics:
        raw = dict(payload or {})
        autonomy_tier = str(raw.get("autonomy_tier") or raw.get("business_autonomy") or raw.get("autonomy") or "supervised").strip()
        capability_policy = _mapping(raw.get("capability_policy") or raw.get("capability"))
        planning_policy = _mapping(raw.get("planning_policy") or raw.get("planning"))
        approval_policy = _mapping(raw.get("approval_policy") or raw.get("approval"))
        self._fail_on_scalar_conflict(raw, canonical_key="autonomy_tier", canonical_value=autonomy_tier, aliases=("business_autonomy", "autonomy"))
        self._fail_on_mapping_conflict(raw, canonical_key="capability_policy", canonical_value=capability_policy, aliases=("capability",))
        self._fail_on_mapping_conflict(raw, canonical_key="planning_policy", canonical_value=planning_policy, aliases=("planning",))
        self._fail_on_mapping_conflict(raw, canonical_key="approval_policy", canonical_value=approval_policy, aliases=("approval",))
        return UnifiedPolicySemantics(
            autonomy_tier=autonomy_tier,
            capability_policy=capability_policy,
            planning_policy=planning_policy,
            approval_policy=approval_policy,
        )

    @staticmethod
    def _fail_on_scalar_conflict(payload: Mapping[str, Any], *, canonical_key: str, canonical_value: object, aliases: tuple[str, ...]) -> None:
        for alias in aliases:
            if alias in payload and canonical_key in payload and str(payload.get(alias)).strip() != str(canonical_value).strip():
                raise ValueError(f"policy semantic conflict: {alias} != {canonical_key}")

    @staticmethod
    def _fail_on_mapping_conflict(payload: Mapping[str, Any], *, canonical_key: str, canonical_value: Mapping[str, Any], aliases: tuple[str, ...]) -> None:
        canonical = _canonical_json(dict(canonical_value or {}))
        for alias in aliases:
            if alias in payload and canonical_key in payload:
                if _canonical_json(_mapping(payload.get(alias))) != canonical:
                    raise ValueError(f"policy semantic conflict: {alias} != {canonical_key}")


__all__ = [
    "CANON_POLICY_SEMANTICS_GUARD",
    "PolicySemanticsGuard",
    "UnifiedPolicySemantics",
]
