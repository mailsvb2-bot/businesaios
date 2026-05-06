from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional

from governance.governance_ai import GovernanceAI

# Tier‑Ω FINAL: governance control‑plane skeleton.
# This is the *meta* layer that can freeze, rollback, or allow normal ops.

@dataclass
class GovernanceDecision:
    action: str  # "ok" | "rollback" | "freeze"
    reason: str

class GovernanceControlPlane:
    def __init__(self, ai: Optional[GovernanceAI] = None):
        self._ai = ai or GovernanceAI()
        self._frozen = False

    @property
    def frozen(self) -> bool:
        return self._frozen

    def evaluate(self, metrics: Dict[str, Any]) -> GovernanceDecision:
        verdict = self._ai.evaluate(metrics)
        if verdict == "rollback":
            return GovernanceDecision("rollback", "revenue_drop")
        if verdict == "freeze":
            return GovernanceDecision("freeze", "anomaly_score")
        return GovernanceDecision("ok", "normal")

    def apply(self, decision: GovernanceDecision, *, registry=None) -> None:
        # registry is expected to provide deploy/rollback/freeze hooks, kept optional for modularity.
        if decision.action == "freeze":
            self._frozen = True
            if registry and hasattr(registry, "freeze"):
                registry.freeze()
        elif decision.action == "rollback":
            if registry and hasattr(registry, "rollback"):
                registry.rollback()
        # "ok" does nothing

    def unfreeze(self) -> None:
        self._frozen = False
