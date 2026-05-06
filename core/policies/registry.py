from __future__ import annotations

import threading
from typing import Dict, Optional

from core.policies.domain import PolicyRef, PolicyStatus


class PolicyRegistry:
    """
    Единый источник правды.

    Инварианты:
    - ровно одна SAFE policy (active)
    - максимум одна CANARY policy
    """

    def __init__(self) -> None:
        self._statuses: Dict[str, PolicyStatus] = {}
        self._active: Optional[PolicyRef] = None
        self._canary: Optional[PolicyRef] = None
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

    def active(self) -> Optional[PolicyRef]:
        return self._active

    def canary(self) -> Optional[PolicyRef]:
        return self._canary

    def status(self, policy_id: str) -> Optional[PolicyStatus]:
        return self._statuses.get(policy_id)
