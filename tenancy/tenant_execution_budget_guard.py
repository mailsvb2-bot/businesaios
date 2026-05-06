from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Mapping

from core.tenancy.normalization import require_tenant_id
from tenancy.tenant_contract import TenantPolicyStoreContract, TenantQuotaCheck, TenantQuotaGuardContract


CANON_TENANT_EXECUTION_BUDGET_GUARD = True


@dataclass(frozen=True)
class TenantExecutionUsage:
    tenant_id: str
    action_count: int = 0
    effect_count: int = 0
    outbound_message_count: int = 0
    publication_count: int = 0
    memory_write_count: int = 0
    connector_call_count: int = 0
    budget_delta: float = 0.0
    labels: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        for field_name in (
            "action_count",
            "effect_count",
            "outbound_message_count",
            "publication_count",
            "memory_write_count",
            "connector_call_count",
        ):
            value = int(getattr(self, field_name))
            if value < 0:
                raise ValueError(f"{field_name} must be >= 0")
        if float(self.budget_delta) < 0:
            raise ValueError("budget_delta must be >= 0")
        for key, value in dict(self.labels).items():
            if not str(key or "").strip():
                raise ValueError("label key must be non-empty")
            if not str(value or "").strip():
                raise ValueError("label value must be non-empty")

    def is_noop(self) -> bool:
        self.validate()
        return (
            self.action_count == 0
            and self.effect_count == 0
            and self.outbound_message_count == 0
            and self.publication_count == 0
            and self.memory_write_count == 0
            and self.connector_call_count == 0
            and float(self.budget_delta) == 0.0
        )


@dataclass(frozen=True)
class TenantRuntimeLimitCheck:
    name: str
    allowed: bool
    requested: float
    limit: float


@dataclass(frozen=True)
class TenantExecutionBudgetVerdict:
    allowed: bool
    reason: str
    tenant_id: str
    violations: tuple[str, ...] = ()
    runtime_limit_checks: Mapping[str, TenantRuntimeLimitCheck] = field(default_factory=dict)
    quota_checks: Mapping[str, TenantQuotaCheck] = field(default_factory=dict)
    consumed: bool = False

    @property
    def denied(self) -> bool:
        return not self.allowed


class TenantExecutionBudgetGuard:
    ACTIONS_PER_DAY = "actions_per_day"
    OUTBOUND_MESSAGES_PER_DAY = "outbound_messages_per_day"
    PUBLICATIONS_PER_DAY = "publications_per_day"
    MEMORY_WRITES_PER_DAY = "memory_writes_per_day"
    CONNECTOR_CALLS_PER_HOUR = "connector_calls_per_hour"
    DAILY_BUDGET = "daily_budget"

    def __init__(
        self,
        *,
        policy_store: TenantPolicyStoreContract,
        quota_guard: TenantQuotaGuardContract,
    ) -> None:
        self._policy_store = policy_store
        self._quota_guard = quota_guard
        self._lock = RLock()

    def evaluate(self, *, usage: TenantExecutionUsage) -> TenantExecutionBudgetVerdict:
        usage.validate()
        tid = require_tenant_id(usage.tenant_id)
        runtime_limits = self._require_runtime_limits(tid)
        runtime_checks: dict[str, TenantRuntimeLimitCheck] = {}
        violations: list[str] = []

        def add_runtime_check(name: str, requested: int | float, limit: int | float) -> None:
            req = float(requested)
            lim = float(limit)
            allowed = req <= lim
            runtime_checks[name] = TenantRuntimeLimitCheck(name=name, allowed=allowed, requested=req, limit=lim)
            if not allowed:
                violations.append(name)

        add_runtime_check("max_actions_per_run", usage.action_count, getattr(runtime_limits, "max_actions_per_run"))
        add_runtime_check("max_effects_per_run", usage.effect_count, getattr(runtime_limits, "max_effects_per_run"))
        add_runtime_check("max_outbound_messages_per_day", usage.outbound_message_count, getattr(runtime_limits, "max_outbound_messages_per_day"))
        add_runtime_check("max_publications_per_day", usage.publication_count, getattr(runtime_limits, "max_publications_per_day"))
        add_runtime_check("max_memory_writes_per_day", usage.memory_write_count, getattr(runtime_limits, "max_memory_writes_per_day"))
        add_runtime_check("max_connector_calls_per_hour", usage.connector_call_count, getattr(runtime_limits, "max_connector_calls_per_hour"))
        add_runtime_check("max_daily_budget", usage.budget_delta, getattr(runtime_limits, "max_daily_budget"))

        requests = self._quota_dimensions_for_usage(usage)
        if hasattr(self._quota_guard, "check_many"):
            quota_checks = dict(getattr(self._quota_guard, "check_many")(tenant_id=tid, requests=requests))
        else:
            quota_checks = {
                dimension: self._quota_guard.check(tenant_id=tid, dimension=dimension, amount=float(amount))
                for dimension, amount in requests
            }
        for dimension, verdict in quota_checks.items():
            if not verdict.allowed:
                violations.append(f"quota:{dimension}")

        return TenantExecutionBudgetVerdict(
            allowed=not violations,
            reason="tenant_execution_budget_allowed" if not violations else "tenant_execution_budget_denied",
            tenant_id=tid,
            violations=tuple(violations),
            runtime_limit_checks=runtime_checks,
            quota_checks=quota_checks,
            consumed=False,
        )

    def consume(self, *, usage: TenantExecutionUsage) -> TenantExecutionBudgetVerdict:
        usage.validate()
        tid = require_tenant_id(usage.tenant_id)
        with self._lock:
            precheck = self.evaluate(usage=usage)
            if not precheck.allowed:
                return precheck
            requests = self._quota_dimensions_for_usage(usage)
            if hasattr(self._quota_guard, "consume_many"):
                consumed_checks = dict(getattr(self._quota_guard, "consume_many")(tenant_id=tid, requests=requests))
            else:
                consumed_checks = {
                    dimension: self._quota_guard.consume(tenant_id=tid, dimension=dimension, amount=float(amount))
                    for dimension, amount in requests
                }
            failed = [f"quota:{dimension}" for dimension, verdict in consumed_checks.items() if not verdict.allowed]
            return TenantExecutionBudgetVerdict(
                allowed=not failed,
                reason="tenant_execution_budget_consumed" if not failed else "tenant_execution_budget_atomic_consume_failed",
                tenant_id=tid,
                violations=tuple(failed),
                runtime_limit_checks=precheck.runtime_limit_checks,
                quota_checks=consumed_checks,
                consumed=not failed,
            )

    @classmethod
    def from_execution_payload(cls, *, tenant_id: str, payload: Mapping[str, object] | None) -> TenantExecutionUsage:
        body = dict(payload or {})

        def _safe_int(value: object) -> int:
            try:
                return max(0, int(value or 0))
            except (TypeError, ValueError):
                return 0

        def _safe_float(value: object) -> float:
            try:
                return max(0.0, float(value or 0.0))
            except (TypeError, ValueError):
                return 0.0

        labels = {
            str(key).strip(): str(value).strip()
            for key, value in dict(body.get("labels") or {}).items()
            if str(key or "").strip() and str(value or "").strip()
        }
        return TenantExecutionUsage(
            tenant_id=require_tenant_id(tenant_id),
            action_count=_safe_int(body.get("action_count", body.get("actions"))),
            effect_count=_safe_int(body.get("effect_count", body.get("effects"))),
            outbound_message_count=_safe_int(body.get("outbound_message_count", body.get("outbound"))),
            publication_count=_safe_int(body.get("publication_count", body.get("publications"))),
            memory_write_count=_safe_int(body.get("memory_write_count", body.get("memory_writes"))),
            connector_call_count=_safe_int(body.get("connector_call_count", body.get("connector_calls"))),
            budget_delta=_safe_float(body.get("budget_delta", body.get("budget_change_amount"))),
            labels=labels,
        )

    def _require_runtime_limits(self, tenant_id: str) -> object:
        bundle = self._policy_store.require(tenant_id)
        runtime_limits = getattr(bundle, "runtime_limits", None)
        if runtime_limits is None:
            raise AttributeError("policy bundle must expose runtime_limits")
        return runtime_limits

    def _quota_dimensions_for_usage(self, usage: TenantExecutionUsage) -> tuple[tuple[str, float], ...]:
        pairs: list[tuple[str, float]] = []
        if usage.action_count > 0:
            pairs.append((self.ACTIONS_PER_DAY, float(usage.action_count)))
        if usage.outbound_message_count > 0:
            pairs.append((self.OUTBOUND_MESSAGES_PER_DAY, float(usage.outbound_message_count)))
        if usage.publication_count > 0:
            pairs.append((self.PUBLICATIONS_PER_DAY, float(usage.publication_count)))
        if usage.memory_write_count > 0:
            pairs.append((self.MEMORY_WRITES_PER_DAY, float(usage.memory_write_count)))
        if usage.connector_call_count > 0:
            pairs.append((self.CONNECTOR_CALLS_PER_HOUR, float(usage.connector_call_count)))
        if usage.budget_delta > 0:
            pairs.append((self.DAILY_BUDGET, float(usage.budget_delta)))
        return tuple(pairs)


__all__ = [
    "CANON_TENANT_EXECUTION_BUDGET_GUARD",
    "TenantExecutionBudgetGuard",
    "TenantExecutionBudgetVerdict",
    "TenantExecutionUsage",
    "TenantRuntimeLimitCheck",
]
