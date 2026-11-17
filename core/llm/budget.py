from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol

from config.llm_budget_policy import DEFAULT_LLM_BUDGET_POLICY, LLMBudgetPolicy
from core.telemetry.event_types import LLM_COMPLETED
from core.telemetry.trace_utils import day_key_utc


@dataclass(frozen=True)
class BudgetCaps:
    policy: LLMBudgetPolicy = field(default_factory=lambda: DEFAULT_LLM_BUDGET_POLICY)
    tenant_tokens_per_day: int = field(default_factory=lambda: DEFAULT_LLM_BUDGET_POLICY.tenant_tokens_per_day)
    user_tokens_per_day: int = field(default_factory=lambda: DEFAULT_LLM_BUDGET_POLICY.user_tokens_per_day)
    tenant_tokens_per_week: int | None = field(default_factory=lambda: DEFAULT_LLM_BUDGET_POLICY.tenant_tokens_per_week)
    user_tokens_per_week: int | None = field(default_factory=lambda: DEFAULT_LLM_BUDGET_POLICY.user_tokens_per_week)
    tenant_tokens_per_month: int | None = field(default_factory=lambda: DEFAULT_LLM_BUDGET_POLICY.tenant_tokens_per_month)
    user_tokens_per_month: int | None = field(default_factory=lambda: DEFAULT_LLM_BUDGET_POLICY.user_tokens_per_month)

    def __post_init__(self) -> None:
        for name in ("tenant_tokens_per_day", "user_tokens_per_day", *(f"{who}_tokens_per_{p}" for p in ("week", "month") for who in ("tenant", "user"))):
            value = getattr(self, name)
            if not (value is None and not name.endswith("_day")) and (type(value) is not int or value < 0):
                raise ValueError(f"LLM_BUDGET_INVALID_CAP:{name}")

    def periods(self) -> tuple[tuple[str, int, int], ...]:
        """(period, tenant_cap, user_cap); week/month appear only when configured."""
        caps = (("day", self.tenant_tokens_per_day, self.user_tokens_per_day),) + tuple(
            (p, getattr(self, f"tenant_tokens_per_{p}"), getattr(self, f"user_tokens_per_{p}")) for p in ("week", "month"))
        return tuple((p, 2**62 if t is None else t, 2**62 if u is None else u) for p, t, u in caps if p == "day" or t is not None or u is not None)


class DailyTokenBudget:
    """Single-process fallback. EventStoreDailyTokenBudget is authoritative across workers."""

    def __init__(self, caps: BudgetCaps) -> None:
        self._caps = caps
        self._tenant: dict[tuple[str, str], int] = {}
        self._user: dict[tuple[str, str, str], int] = {}

    def _day(self) -> str:
        return day_key_utc()

    def can_spend(self, *, tenant_id: str, user_id: str, tokens: int) -> bool:
        day = self._day()
        tenant = self._tenant.get((day, str(tenant_id)), 0)
        user = self._user.get((day, str(tenant_id), str(user_id)), 0)
        if len(self._caps.periods()) > 1:
            return False  # Week/month caps need the durable EventStore budget; never ignore them.
        return tenant + tokens <= self._caps.tenant_tokens_per_day and user + tokens <= self._caps.user_tokens_per_day

    def spend(self, *, tenant_id: str, user_id: str, tokens: int) -> None:
        day = self._day()
        tkey, ukey = (day, str(tenant_id)), (day, str(tenant_id), str(user_id))
        self._tenant[tkey] = self._tenant.get(tkey, 0) + int(tokens)
        self._user[ukey] = self._user.get(ukey, 0) + int(tokens)


class TokenBudget(Protocol):
    def can_spend(self, *, tenant_id: str, user_id: str, tokens: int) -> bool: ...
    def spend(self, *, tenant_id: str, user_id: str, tokens: int) -> None: ...


def _utc_day_bounds_ms(ts_ms: int | None = None) -> tuple[int, int]:
    day = int((int(time.time() * 1000) if ts_ms is None else ts_ms) // 86_400_000)
    return day * 86_400_000, (day + 1) * 86_400_000


def _utc_period_bounds_ms(period: str) -> tuple[int, int]:
    start, end = _utc_day_bounds_ms()
    today = datetime.fromtimestamp(start / 1000, tz=UTC)
    first = {"day": today, "week": today - timedelta(days=today.weekday()), "month": today.replace(day=1)}[period]
    return int(first.timestamp() * 1000), end


def estimate_request_tokens(request: Any) -> int:
    return int(request.max_tokens) + 800 + sum(len(m.content.encode("utf-8")) for m in request.messages)


def validated_llm_usage(usage: Any) -> tuple[int, int, int] | None:
    """Validate provider measurements; never substitute a reservation estimate."""
    values = tuple((usage.get(key) if isinstance(usage, Mapping) else getattr(usage, key, None)) for key in ("prompt_tokens", "completion_tokens", "total_tokens"))
    return values if all(type(v) is int and v >= 0 for v in values) and values[2] > 0 and values[2] >= values[0] + values[1] else None


def validated_llm_completion_event(event: Any) -> tuple[str, str, tuple[int, int, int]] | None:
    if not isinstance(event, dict) or not isinstance(user := event.get("user_id"), str) or not user.strip():
        return None
    if not isinstance(payload := event.get("payload"), dict):
        return None
    request_id, provider, model = (payload.get(key) for key in ("request_id", "provider", "model"))
    usage = validated_llm_usage(payload)
    return (user, request_id, usage) if all(isinstance(v, str) and v.strip() for v in (request_id, provider, model)) and usage is not None else None


def has_durable_budget_store(event_store: Any) -> bool:
    return getattr(event_store, "supports_durable_llm_budget", False) is True and all(
        callable(getattr(event_store, name, None))
        for name in ("iter_events", "get_setting", "compare_and_set_setting", "append_event"))


class EventStoreDailyTokenBudget:
    def __init__(self, *, event_store: Any, caps: BudgetCaps, cache_ttl_s: float = DEFAULT_LLM_BUDGET_POLICY.cache_ttl_seconds) -> None:
        self._es, self._caps = event_store, caps

    def _day(self) -> str:
        return day_key_utc()

    def _sum(self, *, tenant_id: str, user_id: str, period: str = "day") -> tuple[int, int]:
        start_ms, end_ms = _utc_period_bounds_ms(period)
        if not callable(it := getattr(self._es, "iter_events", None)):
            raise RuntimeError("LLM_BUDGET_EVENT_AGGREGATOR_UNAVAILABLE")
        tenant = user = 0
        for event in it(tenant_id=str(tenant_id), start_ms=start_ms, end_ms=end_ms, event_type=LLM_COMPLETED):
            if (fact := validated_llm_completion_event(event)) is None:
                raise RuntimeError("LLM_BUDGET_CORRUPT_COMPLETION")
            tenant, user = tenant + fact[2][2], user + (fact[2][2] if fact[0] == str(user_id) else 0)
        return tenant, user

    def can_spend(self, *, tenant_id: str, user_id: str, tokens: int) -> bool:
        return all(spent_t + tokens <= t_cap and spent_u + tokens <= u_cap for p, t_cap, u_cap in self._caps.periods()
                   for spent_t, spent_u in (self._sum(tenant_id=tenant_id, user_id=user_id, period=p),))

    def spend(self, *, tenant_id: str, user_id: str, tokens: int) -> None:
        return None  # The durable completion is authoritative; no cross-worker cache.

    def _reconcile_completed(self, *, tenant_id: str, day: str, current: dict) -> bool:
        if not callable(it := getattr(self._es, "iter_events", None)) or not isinstance(current, dict) or not isinstance(current.get("pending"), dict):
            return False
        try:
            reservation_day = date.fromisoformat(day)
            if reservation_day.isoformat() != day:
                return False
            start, end = _utc_day_bounds_ms(int(datetime.combine(reservation_day, datetime.min.time(), tzinfo=UTC).timestamp() * 1000))
        except (TypeError, ValueError, OverflowError):
            return False
        completed = set()
        try:
            for event in it(tenant_id=str(tenant_id), start_ms=start, end_ms=end, event_type=LLM_COMPLETED):
                if (fact := validated_llm_completion_event(event)) is None:
                    return False
                completed.add(fact[:2])
        except (TypeError, ValueError, AttributeError):
            return False
        remaining = {rid: row for rid, row in current["pending"].items() if (str(row["user_id"]), rid) not in completed}
        return len(remaining) < len(current["pending"]) and self._es.compare_and_set_setting(tenant_id=str(tenant_id), key=f"llm:pending:v1:{day}", expected=current, value={"pending": remaining})

    def reserve(self, *, tenant_id: str, user_id: str, tokens: int, request_id: str) -> str | None:
        get, cas = getattr(self._es, "get_setting", None), getattr(self._es, "compare_and_set_setting", None)
        if not callable(get) or not callable(cas) or type(tokens) is not int or tokens <= 0 or any(not isinstance(v, str) or not v.strip() for v in (tenant_id, user_id, request_id)):
            return None
        key = f"llm:pending:v1:{(day := self._day())}"
        for _ in range(16):
            if not isinstance(current := get(tenant_id=str(tenant_id), key=key), (dict, type(None))):
                return None
            if not isinstance(pending := (current or {}).get("pending", {}), dict) or request_id in pending:
                return None
            spent = {p: self._sum(tenant_id=tenant_id, user_id=user_id, period=p) for p, _t, _u in self._caps.periods()}
            reserved_tenant = reserved_user = 0
            for rid, row in pending.items():
                if not isinstance(rid, str) or not rid or not isinstance(row, dict):
                    return None
                row_user, row_tokens = row.get("user_id"), row.get("tokens")
                if not isinstance(row_user, str) or not row_user.strip() or type(row_tokens) is not int or row_tokens <= 0:
                    return None
                reserved_tenant, reserved_user = reserved_tenant + row_tokens, reserved_user + (row_tokens if row_user == str(user_id) else 0)
            if self._day() != day:
                return None
            # Today's pending claims count against every period that contains today.
            if any(spent[p][0] + reserved_tenant + tokens > t_cap or spent[p][1] + reserved_user + tokens > u_cap for p, t_cap, u_cap in self._caps.periods()):
                if self._reconcile_completed(tenant_id=tenant_id, day=day, current=current):
                    continue
                return None
            state = {"pending": {**pending, request_id: {"user_id": str(user_id), "tokens": int(tokens)}}}
            if cas(tenant_id=str(tenant_id), key=key, expected=current, value=state):
                claimed = False
                try:
                    claimed = cas(tenant_id=str(tenant_id), key=f"llm:claim:v2:{request_id}", expected=None, value={"user_id": str(user_id)})
                    return day if claimed else None
                finally:
                    if not claimed:
                        self.cancel_unstarted_reservation(tenant_id=tenant_id, request_id=request_id, day=day)
        return None

    def cancel_unstarted_reservation(self, *, tenant_id: str, request_id: str, day: str) -> bool:
        try:
            return self.release(tenant_id=tenant_id, request_id=request_id, day=day)
        except Exception:  # noqa: BLE001
            return False

    def release(self, *, tenant_id: str, request_id: str, day: str) -> bool:
        key = f"llm:pending:v1:{day}"
        for _ in range(16):
            if not isinstance(current := self._es.get_setting(tenant_id=str(tenant_id), key=key), dict):
                return False
            if not isinstance(pending := current.get("pending", {}), dict) or request_id not in pending:
                return False
            remaining = {rid: row for rid, row in pending.items() if rid != request_id}
            if self._es.compare_and_set_setting(tenant_id=str(tenant_id), key=key, expected=current, value={"pending": remaining}):
                return True
        return False
