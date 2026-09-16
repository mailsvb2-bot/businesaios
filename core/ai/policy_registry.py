"""Policy registry.

Single source of truth for policy objects selected by DecisionCore.

IMPORTANT:
- Policy activation / rollout changes are SIDE-EFFECTS and must therefore occur
  ONLY via RuntimeExecutor through deploy_policy/rollback_policy decisions.
- Lifecycle state for active/canary references remains owned by ``core.policies``.
- Concrete policy object storage is local; durable runtime lifecycle state is
  written only through the injected canonical runtime-state store.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from threading import RLock
from typing import Any

from core.ai._policy_registry_store import PolicyRegistryStore, PolicyRuntimeStateStore
from core.policies.registry import PolicyRegistry as _MetaPolicyRegistry
from core.policies.registry import PolicyRegistrySnapshot
from core.policies.types import PolicyRef, PolicyStatus
from core.security.call_origin import assert_called_from_bootstrap, assert_called_from_runtime_executor

CANON_CORE_AI_POLICY_REGISTRY_LOCAL_STORE = True
CANON_POLICY_ENTITY_LIFECYCLE_OWNER = True
POLICY_RUNTIME_STATE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class PolicyRuntimeStateSnapshot:
    lifecycle: PolicyRegistrySnapshot
    previous_policy_id: str | None
    candidate_policy_id: str | None
    rollout_pct: int
    governed_candidate_policy_id: str | None
    rollout_generation: int


class PolicyRegistry:
    def __init__(self, *, runtime_state_store: PolicyRuntimeStateStore | None = None):
        self._policies = PolicyRegistryStore()
        self._meta = _MetaPolicyRegistry()
        self._previous: str | None = None
        self._candidate: str | None = None
        self._rollout_pct: int = 0
        self._governed_candidate: str | None = None
        self._rollout_generation: int = 0
        self._rollout_lock = RLock()
        self._runtime_state_store = runtime_state_store

    @staticmethod
    def _policy_ref(policy) -> PolicyRef:
        policy_id = str(getattr(policy, "id", "") or "").strip()
        if not policy_id:
            raise ValueError("EMPTY_POLICY_ID")
        base, separator, version = policy_id.rpartition("@")
        if not separator or not base or not version.startswith("v") or len(version) <= 1:
            raise ValueError("POLICY_ID_MUST_BE_VERSIONED")
        if not version[1:].replace(".", "").replace("-", "").replace("_", "").isalnum():
            raise ValueError("INVALID_POLICY_VERSION")
        return PolicyRef(policy_id=policy_id, version=version)

    @staticmethod
    def _ref_payload(ref: PolicyRef | None) -> dict[str, str] | None:
        if ref is None:
            return None
        return {"policy_id": str(ref.policy_id), "version": str(ref.version)}

    @staticmethod
    def _ref_from_payload(value: object) -> PolicyRef | None:
        if value is None:
            return None
        if not isinstance(value, Mapping):
            raise ValueError("POLICY_RUNTIME_STATE_REF_INVALID")
        policy_id = str(value.get("policy_id") or "").strip()
        version = str(value.get("version") or "").strip()
        if not policy_id or not version:
            raise ValueError("POLICY_RUNTIME_STATE_REF_INVALID")
        return PolicyRef(policy_id=policy_id, version=version)

    def _registered_ref(self, policy_id: str) -> PolicyRef:
        policy = self._policies.get(str(policy_id).strip())
        return self._policy_ref(policy)

    def _snapshot_unlocked(self) -> PolicyRuntimeStateSnapshot:
        return PolicyRuntimeStateSnapshot(
            lifecycle=self._meta.snapshot(),
            previous_policy_id=self._previous,
            candidate_policy_id=self._candidate,
            rollout_pct=int(self._rollout_pct),
            governed_candidate_policy_id=self._governed_candidate,
            rollout_generation=int(self._rollout_generation),
        )

    def _snapshot_payload(self, snapshot: PolicyRuntimeStateSnapshot) -> dict[str, Any]:
        return {
            "schema_version": POLICY_RUNTIME_STATE_SCHEMA_VERSION,
            "lifecycle": {
                "statuses": {
                    str(policy_id): status.value
                    for policy_id, status in sorted(snapshot.lifecycle.statuses.items())
                },
                "active": self._ref_payload(snapshot.lifecycle.active),
                "canary": self._ref_payload(snapshot.lifecycle.canary),
            },
            "previous_policy_id": snapshot.previous_policy_id,
            "candidate_policy_id": snapshot.candidate_policy_id,
            "rollout_pct": int(snapshot.rollout_pct),
            "governed_candidate_policy_id": snapshot.governed_candidate_policy_id,
            "rollout_generation": int(snapshot.rollout_generation),
        }

    def _snapshot_from_payload(self, payload: Mapping[str, Any]) -> PolicyRuntimeStateSnapshot:
        if payload.get("schema_version") != POLICY_RUNTIME_STATE_SCHEMA_VERSION:
            raise ValueError("POLICY_RUNTIME_STATE_SCHEMA_UNSUPPORTED")
        lifecycle_raw = payload.get("lifecycle")
        if not isinstance(lifecycle_raw, Mapping):
            raise ValueError("POLICY_RUNTIME_STATE_LIFECYCLE_INVALID")
        statuses_raw = lifecycle_raw.get("statuses")
        if not isinstance(statuses_raw, Mapping):
            raise ValueError("POLICY_RUNTIME_STATE_STATUSES_INVALID")
        statuses: dict[str, PolicyStatus] = {}
        for policy_id, raw_status in statuses_raw.items():
            normalized_id = str(policy_id or "").strip()
            if not normalized_id:
                raise ValueError("POLICY_RUNTIME_STATE_STATUS_ID_INVALID")
            try:
                statuses[normalized_id] = PolicyStatus(str(raw_status))
            except ValueError as exc:
                raise ValueError("POLICY_RUNTIME_STATE_STATUS_INVALID") from exc
        pct = payload.get("rollout_pct")
        generation = payload.get("rollout_generation")
        if isinstance(pct, bool) or not isinstance(pct, int) or pct < 0 or pct > 100:
            raise ValueError("POLICY_RUNTIME_STATE_ROLLOUT_INVALID")
        if isinstance(generation, bool) or not isinstance(generation, int) or generation < 0:
            raise ValueError("POLICY_RUNTIME_STATE_GENERATION_INVALID")
        return PolicyRuntimeStateSnapshot(
            lifecycle=PolicyRegistrySnapshot(
                statuses=statuses,
                active=self._ref_from_payload(lifecycle_raw.get("active")),
                canary=self._ref_from_payload(lifecycle_raw.get("canary")),
            ),
            previous_policy_id=self._optional_policy_id(payload.get("previous_policy_id")),
            candidate_policy_id=self._optional_policy_id(payload.get("candidate_policy_id")),
            rollout_pct=pct,
            governed_candidate_policy_id=self._optional_policy_id(payload.get("governed_candidate_policy_id")),
            rollout_generation=generation,
        )

    @staticmethod
    def _optional_policy_id(value: object) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("POLICY_RUNTIME_STATE_POLICY_ID_INVALID")
        return normalized

    def _validate_snapshot(self, snapshot: PolicyRuntimeStateSnapshot) -> None:
        if not isinstance(snapshot, PolicyRuntimeStateSnapshot):
            raise TypeError("snapshot must be PolicyRuntimeStateSnapshot")
        if snapshot.lifecycle.active is None:
            raise ValueError("POLICY_RUNTIME_STATE_ACTIVE_REQUIRED")
        refs = tuple(ref for ref in (snapshot.lifecycle.active, snapshot.lifecycle.canary) if ref is not None)
        for ref in refs:
            if ref != self._registered_ref(ref.policy_id):
                raise ValueError("POLICY_SNAPSHOT_VERSION_MISMATCH")
        for policy_id in snapshot.lifecycle.statuses:
            self._registered_ref(policy_id)
        for policy_id in (snapshot.previous_policy_id, snapshot.candidate_policy_id, snapshot.governed_candidate_policy_id):
            if policy_id is not None:
                self._registered_ref(policy_id)
        if snapshot.rollout_pct > 0:
            if snapshot.candidate_policy_id is None or snapshot.lifecycle.canary is None:
                raise ValueError("POLICY_RUNTIME_STATE_CANARY_REQUIRED")
            if snapshot.lifecycle.canary.policy_id != snapshot.candidate_policy_id:
                raise ValueError("POLICY_RUNTIME_STATE_CANARY_MISMATCH")
        elif snapshot.lifecycle.canary is not None:
            raise ValueError("POLICY_RUNTIME_STATE_INACTIVE_CANARY")

    def _apply_snapshot_unlocked(self, snapshot: PolicyRuntimeStateSnapshot) -> None:
        self._meta.restore(snapshot.lifecycle)
        self._previous = snapshot.previous_policy_id
        self._candidate = snapshot.candidate_policy_id
        self._rollout_pct = int(snapshot.rollout_pct)
        self._governed_candidate = snapshot.governed_candidate_policy_id
        self._rollout_generation = int(snapshot.rollout_generation)

    def _persist_unlocked(self, snapshot: PolicyRuntimeStateSnapshot, *, expected_generation: int) -> None:
        if self._runtime_state_store is None:
            return
        self._runtime_state_store.save(
            self._snapshot_payload(snapshot),
            expected_generation=int(expected_generation),
        )

    def register(self, policy) -> None:
        """Register one versioned policy during canonical bootstrap wiring."""
        assert_called_from_bootstrap()
        ref = self._policy_ref(policy)
        self._policies.replace(ref.policy_id, policy)
        if self._meta.active() is None:
            self._meta.promote(ref)

    def activate_bootstrap(self, *, policy_id: str) -> None:
        """Select a deterministic fallback before durable runtime state restore."""
        assert_called_from_bootstrap()
        pid = str(policy_id).strip()
        if not pid:
            raise ValueError("EMPTY_POLICY_ID")
        self._meta.promote(self._registered_ref(pid))

    def restore_persisted_runtime_state(self) -> bool:
        """Restore one durable runtime lifecycle snapshot during bootstrap."""
        assert_called_from_bootstrap()
        if self._runtime_state_store is None:
            return False
        payload = self._runtime_state_store.load()
        if payload is None:
            return False
        if not isinstance(payload, Mapping):
            raise ValueError("POLICY_RUNTIME_STATE_PAYLOAD_INVALID")
        snapshot = self._snapshot_from_payload(payload)
        self._validate_snapshot(snapshot)
        with self._rollout_lock:
            self._apply_snapshot_unlocked(snapshot)
        return True

    def get(self, pid: str):
        return self._policies.get(pid)

    def maybe_get(self, pid: str):
        key = str(pid).strip()
        if not key:
            return None
        return self._policies.maybe_get(key)

    def registered_policy_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._policies.keys()))

    def active(self):
        ref = self._meta.active()
        if ref is None:
            raise RuntimeError("NO_ACTIVE_POLICY")
        return self._policies.get(ref.policy_id)

    def active_ref(self) -> PolicyRef:
        with self._rollout_lock:
            ref = self._meta.active()
            if ref is None:
                raise RuntimeError("NO_ACTIVE_POLICY")
            return ref

    @contextmanager
    def live_canary_assignment_window(self) -> Iterator[None]:
        with self._rollout_lock:
            yield

    def rollout_config(self) -> tuple[str | None, int]:
        with self._rollout_lock:
            return self._candidate, int(self._rollout_pct)

    def rollout_generation(self) -> int:
        with self._rollout_lock:
            return int(self._rollout_generation)

    def governed_candidate_identity(self) -> str | None:
        with self._rollout_lock:
            return self._governed_candidate or self._candidate

    def snapshot_runtime_state(self) -> PolicyRuntimeStateSnapshot:
        assert_called_from_runtime_executor()
        with self._rollout_lock:
            return self._snapshot_unlocked()

    def restore_runtime_state(self, snapshot: PolicyRuntimeStateSnapshot) -> None:
        assert_called_from_runtime_executor()
        self._validate_snapshot(snapshot)
        with self._rollout_lock:
            current = self._snapshot_unlocked()
            if self._runtime_state_store is None:
                self._apply_snapshot_unlocked(snapshot)
                return
            if snapshot.rollout_generation > current.rollout_generation:
                raise ValueError("POLICY_RUNTIME_STATE_FUTURE_SNAPSHOT")
            if snapshot == current:
                return
            restored = replace(snapshot, rollout_generation=current.rollout_generation + 1)
            self._apply_snapshot_unlocked(restored)
            try:
                self._persist_unlocked(restored, expected_generation=current.rollout_generation)
            except Exception:
                self._apply_snapshot_unlocked(current)
                raise

    def set_rollout(self, *, candidate_policy_id: str, rollout_pct: int) -> None:
        assert_called_from_runtime_executor()
        pid = str(candidate_policy_id)
        pct = int(rollout_pct)
        with self._rollout_lock:
            if self._policies.maybe_get(pid) is None:
                raise KeyError(pid)
            if pct < 0 or pct > 100:
                raise ValueError("BAD_ROLLOUT_PCT")
            before = self._snapshot_unlocked()
            try:
                self._governed_candidate = pid
                if pct >= 100:
                    self._previous = self._meta.active().policy_id if self._meta.active() else None
                    self._meta.promote(self._registered_ref(pid))
                    self._candidate = None
                    self._rollout_pct = 0
                else:
                    candidate_ref = self._registered_ref(pid)
                    if pct == 0:
                        self._meta.rollback()
                    self._meta.register_candidate(candidate_ref)
                    if pct > 0:
                        self._meta.start_canary(candidate_ref)
                    self._candidate = pid
                    self._rollout_pct = pct
                self._rollout_generation += 1
                after = self._snapshot_unlocked()
                self._validate_snapshot(after)
                self._persist_unlocked(after, expected_generation=before.rollout_generation)
            except Exception:
                self._apply_snapshot_unlocked(before)
                raise

    def rollback(self) -> None:
        assert_called_from_runtime_executor()
        with self._rollout_lock:
            before = self._snapshot_unlocked()
            try:
                self._candidate = None
                self._rollout_pct = 0
                self._meta.rollback()
                self._rollout_generation += 1
                if self._previous is not None:
                    self._meta.promote(self._registered_ref(self._previous))
                after = self._snapshot_unlocked()
                self._validate_snapshot(after)
                self._persist_unlocked(after, expected_generation=before.rollout_generation)
            except Exception:
                self._apply_snapshot_unlocked(before)
                raise

    def canary_ref(self) -> PolicyRef | None:
        return self._meta.canary()


__all__ = [
    "CANON_POLICY_ENTITY_LIFECYCLE_OWNER",
    "POLICY_RUNTIME_STATE_SCHEMA_VERSION",
    "PolicyRegistry",
    "PolicyRuntimeStateSnapshot",
]
