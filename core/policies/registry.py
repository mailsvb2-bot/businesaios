from __future__ import annotations

import threading
from dataclasses import dataclass

from core.policies.domain import PolicyRef, PolicyStatus


@dataclass(frozen=True)
class PolicyRegistrySnapshot:
    statuses: dict[str, PolicyStatus]
    active: PolicyRef | None
    canary: PolicyRef | None


class PolicyRegistry:
    """
    Единый источник правды.

    Инварианты:
    - ровно одна SAFE policy (active)
    - максимум одна CANARY policy
    """

    def __init__(self) -> None:
        self._statuses: dict[str, PolicyStatus] = {}
        self._active: PolicyRef | None = None
        self._canary: PolicyRef | None = None
        self._lock = threading.Lock()

    def register_candidate(self, ref: PolicyRef) -> None:
        with self._lock:
            self._statuses[ref.policy_id] = PolicyStatus.CANDIDATE

    def promote(self, ref: PolicyRef) -> None:
        with self._lock:
            self._active = ref
            self._canary = None
            self._statuses[ref.policy_id] = PolicyStatus.SAFE

    def start_canary(self, ref: PolicyRef) -> None:
        with self._lock:
            if not self._active:
                raise RuntimeError("No active policy")
            self._canary = ref
            self._statuses[ref.policy_id] = PolicyStatus.CANARY

    def rollback(self) -> None:
        with self._lock:
            if self._canary:
                self._statuses[self._canary.policy_id] = PolicyStatus.ROLLED_BACK
            self._canary = None

    def snapshot(self) -> PolicyRegistrySnapshot:
        with self._lock:
            return PolicyRegistrySnapshot(
                statuses=dict(self._statuses),
                active=self._active,
                canary=self._canary,
            )

    def restore(self, snapshot: PolicyRegistrySnapshot) -> None:
        if not isinstance(snapshot, PolicyRegistrySnapshot):
            raise TypeError("snapshot must be PolicyRegistrySnapshot")
        with self._lock:
            self._statuses = dict(snapshot.statuses)
            self._active = snapshot.active
            self._canary = snapshot.canary

    def active(self) -> PolicyRef | None:
        return self._active

    def canary(self) -> PolicyRef | None:
        return self._canary

    def status(self, policy_id: str) -> PolicyStatus | None:
        return self._statuses.get(policy_id)


__all__ = ["PolicyRegistry", "PolicyRegistrySnapshot"]
