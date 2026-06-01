from __future__ import annotations

"""Capability-aware throttle policy for queue claims.

Operational only:
- limits claim throughput for already-decided work;
- does not decide whether a capability should be used;
- separates preview from commit to keep telemetry truthful.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import RLock
from typing import Iterable, Mapping

from core.tenancy.normalization import require_tenant_id
from runtime.queue.job_contract import normalize_now, utc_now

CANON_RUNTIME_QUEUE_CAPABILITY_THROTTLE_POLICY = True


def normalize_capability_key(value: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        raise ValueError("capability is required")
    return text


def resolve_capability_key(
    *,
    capability: str | None = None,
    job_type: str | None = None,
    payload: Mapping[str, object] | None = None,
    tags: Iterable[str] | None = None,
) -> str:
    if capability:
        return normalize_capability_key(capability)
    payload_dict = dict(payload or {})
    for key in ("capability", "capability_key", "action_class", "action_type"):
        candidate = str(payload_dict.get(key) or "").strip()
        if candidate:
            return normalize_capability_key(candidate)
    for tag in tuple(tags or ()):
        text = str(tag).strip()
        if text.startswith("capability:"):
            return normalize_capability_key(text.split(":", 1)[1])
    if job_type:
        return normalize_capability_key(job_type)
    raise ValueError("capability could not be resolved")


@dataclass(frozen=True)
class CapabilityThrottleRule:
    capability: str
    max_claims_per_window: int
    window_seconds: int = 60
    burst_claims: int = 0
    max_active_claims: int | None = None
    retry_after_floor_seconds: int = 1
    tenant_overrides: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "capability", normalize_capability_key(self.capability))
        object.__setattr__(self, "max_claims_per_window", int(self.max_claims_per_window))
        object.__setattr__(self, "window_seconds", int(self.window_seconds))
        object.__setattr__(self, "burst_claims", int(self.burst_claims))
        object.__setattr__(self, "retry_after_floor_seconds", int(self.retry_after_floor_seconds))
        if self.max_claims_per_window < 1:
            raise ValueError("max_claims_per_window must be >= 1")
        if self.window_seconds < 1:
            raise ValueError("window_seconds must be >= 1")
        if self.burst_claims < 0:
            raise ValueError("burst_claims must be >= 0")
        if self.retry_after_floor_seconds < 0:
            raise ValueError("retry_after_floor_seconds must be >= 0")
        if self.max_active_claims is not None:
            object.__setattr__(self, "max_active_claims", int(self.max_active_claims))
            if self.max_active_claims < 1:
                raise ValueError("max_active_claims must be >= 1 when provided")
        normalized_overrides = {}
        for tenant_id, override in dict(self.tenant_overrides).items():
            normalized_overrides[require_tenant_id(tenant_id)] = int(override)
            if int(override) < 1:
                raise ValueError("tenant override must be >= 1")
        object.__setattr__(self, "tenant_overrides", normalized_overrides)


@dataclass(frozen=True)
class CapabilityThrottleVerdict:
    allowed: bool
    reason: str
    capability: str
    tenant_id: str
    queue_name: str
    requested_claims: int
    allowed_claims: int
    active_claims: int
    remaining_in_window: int
    retry_after_seconds: int = 0


@dataclass
class _WindowState:
    used: int = 0
    resets_at: datetime = field(default_factory=utc_now)


class CapabilityThrottlePolicy:
    def __init__(
        self,
        *,
        default_rule: CapabilityThrottleRule | None = None,
        rules: Iterable[CapabilityThrottleRule] = (),
    ) -> None:
        self._default_rule = default_rule or CapabilityThrottleRule(
            capability="default",
            max_claims_per_window=1_000_000,
            window_seconds=60,
            burst_claims=0,
            max_active_claims=None,
            retry_after_floor_seconds=1,
        )
        self._rules: dict[str, CapabilityThrottleRule] = {self._default_rule.capability: self._default_rule}
        self._windows: dict[tuple[str, str, str], _WindowState] = {}
        self._lock = RLock()
        for rule in tuple(rules):
            self.register(rule)

    def register(self, rule: CapabilityThrottleRule) -> CapabilityThrottleRule:
        normalized = CapabilityThrottleRule(
            capability=normalize_capability_key(rule.capability),
            max_claims_per_window=int(rule.max_claims_per_window),
            window_seconds=int(rule.window_seconds),
            burst_claims=int(rule.burst_claims),
            max_active_claims=None if rule.max_active_claims is None else int(rule.max_active_claims),
            retry_after_floor_seconds=int(rule.retry_after_floor_seconds),
            tenant_overrides={require_tenant_id(k): int(v) for k, v in dict(rule.tenant_overrides).items()},
        )
        with self._lock:
            self._rules[normalized.capability] = normalized
        return normalized

    def preview(
        self,
        *,
        tenant_id: str,
        queue_name: str,
        capability: str,
        requested_claims: int,
        active_claims: int = 0,
        now: datetime | None = None,
    ) -> CapabilityThrottleVerdict:
        moment = normalize_now(now)
        tid = require_tenant_id(tenant_id)
        qn = str(queue_name).strip()
        if not qn:
            raise ValueError("queue_name is required")
        cap = normalize_capability_key(capability)
        requested = max(1, int(requested_claims))
        active = max(0, int(active_claims))
        rule = self._rule_for(cap)
        window_limit = self._limit_for(rule=rule, tenant_id=tid)
        if rule.max_active_claims is not None and active >= int(rule.max_active_claims):
            return CapabilityThrottleVerdict(False, "capability_active_claims_exceeded", cap, tid, qn, requested, 0, active, window_limit, max(1, int(rule.retry_after_floor_seconds)))
        with self._lock:
            window = self._window_for_locked(tenant_id=tid, queue_name=qn, capability=cap, rule=rule, now=moment)
            effective_limit = int(window_limit) + int(rule.burst_claims)
            remaining = max(0, effective_limit - int(window.used))
            if remaining <= 0:
                retry_after = max(1, int((window.resets_at - moment).total_seconds()))
                return CapabilityThrottleVerdict(False, "capability_window_exhausted", cap, tid, qn, requested, 0, active, 0, max(retry_after, int(rule.retry_after_floor_seconds)))
            allowed = min(requested, remaining)
            return CapabilityThrottleVerdict(allowed > 0, "capability_allowed" if allowed == requested else "capability_partially_throttled", cap, tid, qn, requested, int(allowed), active, remaining, 0)

    def commit(
        self,
        *,
        tenant_id: str,
        queue_name: str,
        capability: str,
        consumed_claims: int,
        now: datetime | None = None,
    ) -> int:
        moment = normalize_now(now)
        tid = require_tenant_id(tenant_id)
        qn = str(queue_name).strip()
        if not qn:
            raise ValueError("queue_name is required")
        cap = normalize_capability_key(capability)
        consumed = max(0, int(consumed_claims))
        if consumed == 0:
            return 0
        rule = self._rule_for(cap)
        with self._lock:
            window = self._window_for_locked(tenant_id=tid, queue_name=qn, capability=cap, rule=rule, now=moment)
            effective_limit = int(self._limit_for(rule=rule, tenant_id=tid)) + int(rule.burst_claims)
            remaining = max(0, effective_limit - int(window.used))
            actual = min(consumed, remaining)
            window.used += actual
            return actual

    def evaluate_and_consume(self, **kwargs: object) -> CapabilityThrottleVerdict:
        verdict = self.preview(**kwargs)
        if verdict.allowed_claims > 0:
            self.commit(
                tenant_id=verdict.tenant_id,
                queue_name=verdict.queue_name,
                capability=verdict.capability,
                consumed_claims=verdict.allowed_claims,
                now=kwargs.get("now") if isinstance(kwargs.get("now"), datetime) else None,
            )
        return verdict

    def snapshot_window_usage(
        self,
        *,
        tenant_id: str,
        queue_name: str,
        capability: str,
        now: datetime | None = None,
    ) -> tuple[int, datetime]:
        moment = normalize_now(now)
        tid = require_tenant_id(tenant_id)
        qn = str(queue_name).strip()
        if not qn:
            raise ValueError("queue_name is required")
        cap = normalize_capability_key(capability)
        rule = self._rule_for(cap)
        with self._lock:
            window = self._window_for_locked(tenant_id=tid, queue_name=qn, capability=cap, rule=rule, now=moment)
            return int(window.used), window.resets_at

    def reset(self) -> None:
        with self._lock:
            self._windows.clear()

    def _rule_for(self, capability: str) -> CapabilityThrottleRule:
        with self._lock:
            return self._rules.get(capability) or self._default_rule

    @staticmethod
    def _limit_for(*, rule: CapabilityThrottleRule, tenant_id: str) -> int:
        override = dict(rule.tenant_overrides).get(require_tenant_id(tenant_id))
        return max(1, int(rule.max_claims_per_window if override is None else override))

    def _window_for_locked(self, *, tenant_id: str, queue_name: str, capability: str, rule: CapabilityThrottleRule, now: datetime) -> _WindowState:
        key = (tenant_id, queue_name, capability)
        current = self._windows.get(key)
        if current is None or now >= current.resets_at:
            current = _WindowState(used=0, resets_at=now + timedelta(seconds=int(rule.window_seconds)))
            self._windows[key] = current
        return current


__all__ = [
    "CANON_RUNTIME_QUEUE_CAPABILITY_THROTTLE_POLICY",
    "CapabilityThrottlePolicy",
    "CapabilityThrottleRule",
    "CapabilityThrottleVerdict",
    "normalize_capability_key",
    "resolve_capability_key",
]
