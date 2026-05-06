from __future__ import annotations

from typing import Any, Mapping

from core.behavior.operator_policy_catalogs.models import OperatorPolicyCatalog, OperatorPolicyRule
from core.behavior.operators.operator_keys import ALL_OPERATOR_KEYS

_ALLOWED_SET = set(ALL_OPERATOR_KEYS)


def _parse_rule(data: Mapping[str, Any]) -> OperatorPolicyRule:
    allowed = tuple(str(v) for v in (data.get("allowed", []) or []) if str(v) in _ALLOWED_SET)
    denied = tuple(str(v) for v in (data.get("denied", []) or []) if str(v) in _ALLOWED_SET)
    return OperatorPolicyRule(allowed=allowed, denied=denied)


def parse_operator_policy_catalog(data: Mapping[str, Any]) -> OperatorPolicyCatalog:
    by_stage = {str(k): _parse_rule(v or {}) for k, v in (data.get("by_stage", {}) or {}).items()}
    by_role = {str(k): _parse_rule(v or {}) for k, v in (data.get("by_role", {}) or {}).items()}
    by_stage_role = {str(k): _parse_rule(v or {}) for k, v in (data.get("by_stage_role", {}) or {}).items()}
    return OperatorPolicyCatalog(
        catalog_id=str(data.get("catalog_id", "default")),
        by_stage=by_stage,
        by_role=by_role,
        by_stage_role=by_stage_role,
    )
