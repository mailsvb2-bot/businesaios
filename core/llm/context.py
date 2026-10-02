from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ContextSource(StrEnum):
    WORLD_MODEL = "world_model"
    MEMORY = "memory"
    EVIDENCE = "evidence"
    CONSTRAINT = "constraint"


@dataclass(frozen=True)
class ContextFact:
    key: str
    value: Any
    source: str
    evidence_ids: tuple[str, ...] = ()
    observed_at: float | None = None
    privacy_class: str = "internal"
    critical: bool = False

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("context key must be non-empty")
        if not self.source.strip():
            raise ValueError("context source must be non-empty")
        if not self.privacy_class.strip():
            raise ValueError("privacy_class must be non-empty")
        if self.critical and not self.evidence_ids:
            raise ValueError(f"critical context requires evidence_ids: {self.key}")


@dataclass(frozen=True)
class ContextRequirement:
    source: ContextSource
    key: str

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("context requirement key must be non-empty")


@dataclass(frozen=True)
class ContextBudget:
    token_budget: int
    privacy_budget: frozenset[str] = field(
        default_factory=lambda: frozenset({"public", "internal", "confidential"})
    )
    max_age_seconds: float | None = None

    def __post_init__(self) -> None:
        if int(self.token_budget) <= 0:
            raise ValueError("token_budget must be positive")
        if not self.privacy_budget:
            raise ValueError("privacy_budget must be non-empty")
        if self.max_age_seconds is not None and float(self.max_age_seconds) < 0:
            raise ValueError("max_age_seconds must be non-negative")


@dataclass(frozen=True)
class ContextBundle:
    task: str
    facts: tuple[ContextFact, ...]
    estimated_tokens: int

    def as_payload(self) -> dict[str, Any]:
        return {fact.key: fact.value for fact in self.facts}

    def provenance(self) -> dict[str, dict[str, Any]]:
        return {
            fact.key: {
                "source": fact.source,
                "evidence_ids": list(fact.evidence_ids),
                "observed_at": fact.observed_at,
                "privacy_class": fact.privacy_class,
            }
            for fact in self.facts
        }


class ContextBudgetExceeded(RuntimeError):
    pass


class ContextFreshnessViolation(RuntimeError):
    pass


class ContextPrivacyViolation(RuntimeError):
    pass


class ContextBuilder:
    @staticmethod
    def _estimate_tokens(fact: ContextFact) -> int:
        serialized = json.dumps(
            {"key": fact.key, "value": fact.value},
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        return max(1, (len(serialized) + 3) // 4)

    def build(
        self,
        *,
        task: str,
        requirements: Sequence[ContextRequirement],
        world_model: Mapping[str, ContextFact] | None = None,
        memory: Mapping[str, ContextFact] | None = None,
        evidence: Mapping[str, ContextFact] | None = None,
        constraints: Mapping[str, ContextFact] | None = None,
        budget: ContextBudget,
        now_s: float | None = None,
    ) -> ContextBundle:
        sources = {
            ContextSource.WORLD_MODEL: dict(world_model or {}),
            ContextSource.MEMORY: dict(memory or {}),
            ContextSource.EVIDENCE: dict(evidence or {}),
            ContextSource.CONSTRAINT: dict(constraints or {}),
        }
        selected: list[ContextFact] = []
        used_tokens = 0
        seen: set[tuple[ContextSource, str]] = set()

        for requirement in requirements:
            identity = (requirement.source, requirement.key)
            if identity in seen:
                continue
            seen.add(identity)
            fact = sources[requirement.source].get(requirement.key)
            if fact is None:
                continue
            if fact.privacy_class not in budget.privacy_budget:
                raise ContextPrivacyViolation(
                    f"context privacy class is outside budget: {fact.key}:{fact.privacy_class}"
                )
            if (
                budget.max_age_seconds is not None
                and fact.observed_at is not None
                and now_s is not None
                and now_s - fact.observed_at > budget.max_age_seconds
            ):
                raise ContextFreshnessViolation(f"context fact is stale: {fact.key}")
            tokens = self._estimate_tokens(fact)
            if used_tokens + tokens > budget.token_budget:
                raise ContextBudgetExceeded(
                    f"context token budget exceeded by required fact: {fact.key}"
                )
            selected.append(fact)
            used_tokens += tokens

        return ContextBundle(
            task=str(task),
            facts=tuple(selected),
            estimated_tokens=used_tokens,
        )


__all__ = [
    "ContextBudget",
    "ContextBudgetExceeded",
    "ContextBuilder",
    "ContextBundle",
    "ContextFact",
    "ContextFreshnessViolation",
    "ContextPrivacyViolation",
    "ContextRequirement",
    "ContextSource",
]
