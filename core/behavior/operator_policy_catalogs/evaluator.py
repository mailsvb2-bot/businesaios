from __future__ import annotations

from core.behavior.operator_policy_catalogs.models import OperatorPolicyCatalog, OperatorPolicyRule


def is_operator_allowed(
    catalog: OperatorPolicyCatalog | None,
    operator_key: str,
    funnel_stage: str | None,
    actor_role: str | None,
) -> bool:
    if catalog is None:
        return True
    rules = _resolve_rules(catalog, funnel_stage=funnel_stage, actor_role=actor_role)
    for rule in rules:
        if rule.denied and operator_key in rule.denied:
            return False
        if rule.allowed and operator_key not in rule.allowed:
            return False
    return True


def _resolve_rules(catalog: OperatorPolicyCatalog, funnel_stage: str | None, actor_role: str | None) -> list[OperatorPolicyRule]:
    rules: list[OperatorPolicyRule] = []
    if funnel_stage and actor_role:
        rules.append(catalog.by_stage_role.get(f"{funnel_stage}:{actor_role}", OperatorPolicyRule()))
    if funnel_stage:
        rules.append(catalog.by_stage.get(funnel_stage, OperatorPolicyRule()))
    if actor_role:
        rules.append(catalog.by_role.get(actor_role, OperatorPolicyRule()))
    return rules
