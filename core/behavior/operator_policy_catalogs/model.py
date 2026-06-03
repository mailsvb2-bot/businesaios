from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Set
from collections.abc import Iterable, Mapping


@dataclass(frozen=True)
class OperatorPolicyContext:
    """Runtime context for policy checks."""

    funnel_stage: str | None = None  # e.g. discovery/consideration/decision/onboarding/retention
    actor_role: str | None = None    # e.g. decision_maker/champion/user/finance/it


@dataclass(frozen=True)
class OperatorPolicyRule:
    """Allow/deny sets for a context slice."""

    allow: set[str] = field(default_factory=set)
    deny: set[str] = field(default_factory=set)

    def is_allowed(self, operator_key: str) -> bool:
        if operator_key in self.deny:
            return False
        if not self.allow or "*" in self.allow:
            return True
        return operator_key in self.allow


@dataclass(frozen=True)
class OperatorPolicyCatalog:
    """A catalog of policy rules.

    A catalog may specify:
    - defaults: base rule
    - per funnel stage rules
    - per actor role rules
    - per (stage, role) overrides
    """

    name: str
    version: int
    defaults: OperatorPolicyRule = field(default_factory=OperatorPolicyRule)
    stages: Mapping[str, OperatorPolicyRule] = field(default_factory=dict)
    roles: Mapping[str, OperatorPolicyRule] = field(default_factory=dict)
    stage_role: Mapping[str, Mapping[str, OperatorPolicyRule]] = field(default_factory=dict)

    def is_allowed(self, operator_key: str, *, ctx: OperatorPolicyContext) -> bool:
        # Start with defaults
        allowed = self.defaults.is_allowed(operator_key)

        # Apply stage rule
        if ctx.funnel_stage:
            rule = self.stages.get(ctx.funnel_stage)
            if rule is not None:
                allowed = allowed and rule.is_allowed(operator_key)

        # Apply role rule
        if ctx.actor_role:
            rule = self.roles.get(ctx.actor_role)
            if rule is not None:
                allowed = allowed and rule.is_allowed(operator_key)

        # Apply (stage, role) override last (strongest)
        if ctx.funnel_stage and ctx.actor_role:
            rule = self.stage_role.get(ctx.funnel_stage, {}).get(ctx.actor_role)
            if rule is not None:
                allowed = rule.is_allowed(operator_key)

        return bool(allowed)

    def validate_operator_keys(self, canonical_keys: Iterable[str]) -> None:
        canon = set(canonical_keys)

        def _check(rule: OperatorPolicyRule, where: str) -> None:
            unknown = (rule.allow | rule.deny) - canon - {"*"}
            if unknown:
                raise ValueError(f"OperatorPolicyCatalog {self.name}: unknown operator keys in {where}: {sorted(unknown)}")

        _check(self.defaults, "defaults")
        for k, r in self.stages.items():
            _check(r, f"stages.{k}")
        for k, r in self.roles.items():
            _check(r, f"roles.{k}")
        for s, by_role in self.stage_role.items():
            for rname, r in by_role.items():
                _check(r, f"stage_role.{s}.{rname}")
