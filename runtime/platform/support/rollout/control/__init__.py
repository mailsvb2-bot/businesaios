from __future__ import annotations

"""Canonical rollout control surface with compat alias submodules."""

class RolloutAdmission:
    def admit(self, current_steps: int, budget_steps: int) -> bool:
        return current_steps < budget_steps

class RolloutCancellation:
    def should_cancel(self, failed_checks: int) -> bool:
        return failed_checks > 0

class RolloutPriority:
    def sort(self, requests):
        return sorted(requests, key=lambda item: getattr(item, "steps", 0), reverse=True)

class RolloutRecovery:
    def recover(self, failed_rollout_id: str) -> dict[str, str]:
        return {"recovered_rollout_id": failed_rollout_id}

class RolloutRetryPolicy:
    def should_retry(self, attempts: int, max_attempts: int) -> bool:
        return attempts < max_attempts

class RolloutRouter:
    def route(self, workers, request):
        if not workers:
            raise ValueError("No workers available")
        return workers[0], request

class RolloutScheduler:
    def schedule(self, requests):
        return list(requests)

class RolloutThrottling:
    def throttle(self, current: int, maximum: int) -> int:
        return min(current, maximum)

_ALIAS_EXPORTS = {
    "rollout_admission": "RolloutAdmission",
    "rollout_cancellation": "RolloutCancellation",
    "rollout_priority": "RolloutPriority",
    "rollout_recovery": "RolloutRecovery",
    "rollout_retry_policy": "RolloutRetryPolicy",
    "rollout_router": "RolloutRouter",
    "rollout_scheduler": "RolloutScheduler",
    "rollout_throttling": "RolloutThrottling",
}

__all__ = [
    "RolloutAdmission",
    "RolloutCancellation",
    "RolloutPriority",
    "RolloutRecovery",
    "RolloutRetryPolicy",
    "RolloutRouter",
    "RolloutScheduler",
    "RolloutThrottling",
] + list(_ALIAS_EXPORTS)
