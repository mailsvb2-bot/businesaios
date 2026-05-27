from __future__ import annotations

from dataclasses import dataclass

from core.ai.policy_registry import PolicyRegistry
from kernel.world_state import WorldStateV1


@dataclass
class PolicyDeploymentPolicyV1:
    """Meta-policy used by DecisionCore to decide whether to deploy/rollback policies."""

    id: str = "policy_deployment" + "@v1"

    def __init__(self, policy_registry: PolicyRegistry):
        self._policies = policy_registry

    def propose(self, state: WorldStateV1):
        proposal = getattr(state, "deployment_proposal", None) or {}
        kind = proposal.get("kind")
        if kind == "deploy":
            return type(
                "O",
                (),
                {
                    "action": "deploy_policy@v1",
                    "payload": {"candidate_policy_id": proposal["candidate_policy_id"], "rollout_pct": int(proposal["rollout_pct"])},
                },
            )()
        if kind == "rollback":
            return type(
                "O",
                (),
                {"action": "rollback_policy@v1", "payload": {"reason": proposal.get("reason", "guardrail")}},
            )()
        return type("O", (), {"action": "noop@v1", "payload": {}})()
