from __future__ import annotations

from dataclasses import dataclass

CANON_DECISION_CAPABILITY_VOCABULARY = True


@dataclass(frozen=True)
class Capability:
    name: str
    description: str
    advisory_only: bool = True


ALLOWED_ADVISORY_CAPABILITIES: tuple[Capability, ...] = (
    Capability("score", "Rank candidate options without selecting the final winner."),
    Capability("observe", "Collect and normalize evidence for DecisionCore."),
    Capability("validate", "Check candidate consistency, safety and policy fit."),
    Capability("recommend", "Prepare advisory recommendations for DecisionCore."),
    Capability("explain", "Explain evidence and trade-offs without issuing decisions."),
    Capability("guard", "Apply policy and safety constraints before execution."),
    Capability("enrich", "Add context to state before sovereign decisioning."),
    Capability("project", "Estimate likely outcomes without committing execution."),
)

CAPABILITY_BY_NAME = {capability.name: capability for capability in ALLOWED_ADVISORY_CAPABILITIES}


__all__ = [
    "ALLOWED_ADVISORY_CAPABILITIES",
    "CAPABILITY_BY_NAME",
    "CANON_DECISION_CAPABILITY_VOCABULARY",
    "Capability",
]
