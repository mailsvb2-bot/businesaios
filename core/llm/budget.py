from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from config.llm_budget_policy import DEFAULT_LLM_BUDGET_POLICY, LLMBudgetPolicy
from core.telemetry.event_types import LLM_COMPLETED
from core.telemetry.trace_utils import day_key_utc


@dataclass(frozen=True)
class BudgetCaps:
    policy: LLMBudgetPolicy = field(default_factory=lambda: DEFAULT_LLM_BUDGET_POLICY)
    tenant_tokens_per_day: int = field(default_factory=lambda: DEFAULT_LLM_BUDGET_POLICY.tenant_tokens_per_day)
    user_tokens_per_day: int = field(default_factory=lambda: DEFAULT_LLM_BUDGET_POLICY.user_tokens_per_day)


class DailyTokenBudget:
    """In-memory daily budget (no new DB).

    Good for single-node runtime. If multi-node is needed later,
    counters can be moved to event aggregation.
    """

    def __init__(self, caps: BudgetCaps) -> None:
        self._caps = caps
        self._tenant: dict[tuple[str, str], int] = {}
        self._user: dict[tuple[str, str, str], int] = {}

    def _day(self) -> str:
        return day_key_utc()

    def can_spend(self, *, tenant_id: str, user_id: str, tokens: int) -> bool:
        day = self._day()
        tkey = (day, str(tenant_id))
        ukey = (day, str(tenant_id), str(user_id))
        t = int(self._tenant.get(tkey, 0))
        u = int(self._user.get(ukey, 0))
        if t + int(tokens) > int(self._caps.tenant_tokens_per_day):
            return False
        return u + int(tokens) <= int(self._caps.user_tokens_per_day)

    def spend(self, *, tenant_id: str, user_id: str, tokens: int) -> None:
        day = self._day()
        tkey = (day, str(tenant_id))
        ukey = (day, str(tenant_id), str(user_id))
        self._tenant[tkey] = int(self._tenant.get(tkey, 0)) + int(tokens)
        self._user[ukey] = int(self._user.get(ukey, 0)) + int(tokens)


class TokenBudget(Protocol):
    def can_spend(self, *, tenant_id: str, user_id: str, tokens: int) -> bool:
        ...

    def spend(self, *, tenant_id: str, user_id: str, tokens: int) -> None:
        ...


def _utc_day_bounds_ms(ts_ms: int | None = None) -> tuple[int, int]:
    """Return (start_ms, end_ms_exclusive) for UTC day containing ts_ms."""
    if ts_ms is None:
        ts_ms = int(time.time() * 1000)
    # Safer: compute start using integer days from epoch in UTC.
    day = int(ts_ms // (24 * 3600 * 1000))
    start = day * 24 * 3600 * 1000
    end = start + 24 * 3600 * 1000
    return start, end


class EventStoreDailyTokenBudget:
    """Daily budget backed by event_store aggregation.

    This is the canonical multi-node-friendly option:
    - no in-memory divergence between workers
    - source of truth: event_store events
    """

    def __init__(self, *, event_store: Any, caps: BudgetCaps, cache_ttl_s: float = DEFAULT_LLM_BUDGET_POLICY.cache_ttl_seconds) -> None:
        self._es = event_store
        self._caps = caps
        self._ttl = float(cache_ttl_s)
        # cache: (day, tenant, user)->(ts, spent_tenant, spent_user)
        self._cache: dict[tuple[str, str, str], tuple[float, int, int]] = {}

    def _day(self) -> str:
        return day_key_utc()

    def _sum(self, *, tenant_id: str, user_id: str, fresh: bool = False) -> tuple[int, int]:
        day = self._day()
        key = (day, str(tenant_id), str(user_id))
        now = time.time()
        cached = self._cache.get(key)
        if not fresh and cached and (now - cached[0]) <= self._ttl:
            return int(cached[1]), int(cached[2])

        start_ms, end_ms = _utc_day_bounds_ms()

        # Prefer native aggregator if available.
        fn = getattr(self._es, "sum_event_payload_int", None)
        if callable(fn):
            spent_tenant = int(
                fn(tenant_id=str(tenant_id), event_type=LLM_COMPLETED, field="total_tokens", start_ms=start_ms, end_ms=end_ms, user_id=None)
            )
            spent_user = int(
                fn(tenant_id=str(tenant_id), event_type=LLM_COMPLETED, field="total_tokens", start_ms=start_ms, end_ms=end_ms, user_id=str(user_id))
            )
        else:
            # Fallback: iterate events and sum.
            spent_tenant = 0
            spent_user = 0
            it = getattr(self._es, "iter_events", None)
            if callable(it):
                for e in it(tenant_id=str(tenant_id), start_ms=start_ms, end_ms=end_ms, user_id=None, event_type=LLM_COMPLETED):
                    try:
                        spent_tenant += int((e.get("payload") or {}).get("total_tokens") or 0)
                    except Exception:
                        continue
                for e in it(tenant_id=str(tenant_id), start_ms=start_ms, end_ms=end_ms, user_id=str(user_id), event_type=LLM_COMPLETED):
                    try:
                        spent_user += int((e.get("payload") or {}).get("total_tokens") or 0)
                    except Exception:
                        continue
            else:
                spent_tenant = 0
                spent_user = 0

        self._cache[key] = (now, spent_tenant, spent_user)
        return spent_tenant, spent_user

    def can_spend(self, *, tenant_id: str, user_id: str, tokens: int) -> bool:
        spent_tenant, spent_user = self._sum(tenant_id=tenant_id, user_id=user_id)
        if spent_tenant + int(tokens) > int(self._caps.tenant_tokens_per_day):
            return False
        return spent_user + int(tokens) <= int(self._caps.user_tokens_per_day)

    def spend(self, *, tenant_id: str, user_id: str, tokens: int) -> None:
        # No-op: spending is recorded via LLM_COMPLETED telemetry events.
        # We still bump local cache to reduce read load.
        day = self._day()
        key = (day, str(tenant_id), str(user_id))
        now = time.time()
        cached = self._cache.get(key)
        if cached:
            self._cache[key] = (now, int(cached[1]) + int(tokens), int(cached[2]) + int(tokens))


    def reserve(self, *, tenant_id: str, user_id: str, tokens: int, request_id: str) -> str | None:
        """Atomically claim estimated headroom using the canonical store settings CAS.

        A pending claim remains until a durable completion is written. Crashes
        therefore consume headroom for the UTC day rather than permit overspend.
        A missing CAS capability fails closed, never reverting to a local lock.
        """
        get = getattr(self._es, "get_setting", None)
        cas = getattr(self._es, "compare_and_set_setting", None)
        if not callable(get) or not callable(cas) or not request_id or tokens <= 0:
            return None
        day = self._day()
        key = f"llm:pending:v1:{day}"
        for _ in range(16):
            current = get(tenant_id=str(tenant_id), key=key)
            if current is not None and not isinstance(current, dict):
                return None
            pending = (current or {}).get("pending", {})
            if not isinstance(pending, dict) or request_id in pending:
                return None
            spent_tenant, spent_user = self._sum(tenant_id=tenant_id, user_id=user_id, fresh=True)
            try:
                reserved_tenant = sum(max(0, int(row["tokens"])) for row in pending.values())
                reserved_user = sum(
                    max(0, int(row["tokens"])) for row in pending.values()
                    if str(row["user_id"]) == str(user_id)
                )
            except (KeyError, TypeError, ValueError):
                return None
            if spent_tenant + reserved_tenant + tokens > self._caps.tenant_tokens_per_day:
                return None
            if spent_user + reserved_user + tokens > self._caps.user_tokens_per_day:
                return None
            if self._day() != day:
                return None
            next_state = {"pending": {
                **pending, request_id: {"user_id": str(user_id), "tokens": int(tokens)},
            }}
            if cas(tenant_id=str(tenant_id), key=key, expected=current, value=next_state):
                # Claim only after headroom is secured. A budget-denied request
                # may be retried later; an already-processed request may not.
                claimed = cas(
                    tenant_id=str(tenant_id),
                    # Claims are request-scoped across UTC day boundaries.
                    # Day-scoped claims allowed a replay to invoke a provider again
                    # after midnight even when the original spend was durable.
                    key=f"llm:claim:v2:{request_id}",
                    expected=None,
                    value={"user_id": str(user_id)},
                )
                if not claimed:
                    self.release(tenant_id=tenant_id, request_id=request_id, day=day)
                    return None
                return day
        return None

    def release(self, *, tenant_id: str, request_id: str, day: str) -> bool:
        """Release only after the corresponding LLM_COMPLETED event is durable."""
        key = f"llm:pending:v1:{day}"
        for _ in range(16):
            current = self._es.get_setting(tenant_id=str(tenant_id), key=key)
            if not isinstance(current, dict):
                return False
            pending = current.get("pending", {})
            if not isinstance(pending, dict) or request_id not in pending:
                return False
            next_pending = dict(pending)
            del next_pending[request_id]
            if self._es.compare_and_set_setting(
                tenant_id=str(tenant_id), key=key,
                expected=current, value={"pending": next_pending},
            ):
                return True
        return False
