from __future__ import annotations

CANON_THIN_HANDLER = True


from typing import Any


class DeployPolicyHandler:
    """Apply a decided deployment.

    IMPORTANT:
    - This handler must be dumb: only applies payload.
    - Any validation/selection here would be a Decision Bypass.
    """

    def __init__(self, policy_registry) -> None:
        self._policy_registry = policy_registry

    def handle(self, payload: dict[str, Any]) -> None:
        policy_id = str(payload["candidate_policy_id"])
        rollout_pct = int(payload.get("rollout_pct", 10))
        self._policy_registry.set_rollout(candidate_policy_id=policy_id, rollout_pct=rollout_pct)
