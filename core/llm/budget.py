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


class EventStoreDailyTokenBudget:
    """Durable daily spend plus atomic pending claims on the canonical event store."""

    def __init__(self, *, event_store: Any, caps: BudgetCaps, cache_ttl_s: float = DEFAULT_LLM_BUDGET_POLICY.cache_ttl_seconds) -> None:
        self._es, self._caps = event_store, caps

    def _day(self) -> str:
        return day_key_utc()

    def _sum(self, *, tenant_id: str, user_id: str) -> tuple[int, int]:
        start_ms, end_ms = _utc_day_bounds_ms()
        fn = getattr(self._es, "sum_event_payload_int", None)
        if callable(fn):
            def total(who):
                return int(fn(tenant_id=str(tenant_id), event_type=LLM_COMPLETED, field="total_tokens",
                              start_ms=start_ms, end_ms=end_ms, user_id=who))
        else:
            it = getattr(self._es, "iter_events", None)
            if not callable(it):
                raise RuntimeError("LLM_BUDGET_EVENT_AGGREGATOR_UNAVAILABLE")

            def total(who):
                count = 0
                for event in it(tenant_id=str(tenant_id), start_ms=start_ms, end_ms=end_ms,
                                user_id=who, event_type=LLM_COMPLETED):
                    try:
                        count += int((event.get("payload") or {}).get("total_tokens") or 0)
                    except (TypeError, ValueError, AttributeError):
                        continue
                return count

        return total(None), total(str(user_id))

    def can_spend(self, *, tenant_id: str, user_id: str, tokens: int) -> bool:
        tenant, user = self._sum(tenant_id=tenant_id, user_id=user_id)
        return tenant + tokens <= self._caps.tenant_tokens_per_day and user + tokens <= self._caps.user_tokens_per_day

    def spend(self, *, tenant_id: str, user_id: str, tokens: int) -> None:
        return None  # The durable completion is authoritative; no cross-worker cache.

    def _reconcile_completed(self, *, tenant_id: str, day: str, current: dict) -> bool:
        """Reclaim only reservations with durable matching provider spend."""
        it = getattr(self._es, "iter_events", None)
        if not callable(it) or not isinstance(current, dict) or not isinstance(current.get("pending"), dict):
            return False
        start, end = _utc_day_bounds_ms()
        completed = {(str(e.get("user_id") or ""), str((e.get("payload") or {}).get("request_id") or ""))
                     for e in it(tenant_id=str(tenant_id), start_ms=start, end_ms=end, event_type=LLM_COMPLETED)
                     if int((e.get("payload") or {}).get("total_tokens") or 0) > 0}
        remaining = {rid: row for rid, row in current["pending"].items() if (str(row["user_id"]), rid) not in completed}
        return len(remaining) < len(current["pending"]) and self._es.compare_and_set_setting(
            tenant_id=str(tenant_id), key=f"llm:pending:v1:{day}", expected=current, value={"pending": remaining})

    def reserve(self, *, tenant_id: str, user_id: str, tokens: int, request_id: str) -> str | None:
        """Atomic headroom reservation; cross-day claim prevents provider replay."""
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
            spent_tenant, spent_user = self._sum(tenant_id=tenant_id, user_id=user_id)
            try:
                reserved_tenant = sum(max(0, int(row["tokens"])) for row in pending.values())
                reserved_user = sum(max(0, int(row["tokens"])) for row in pending.values()
                                    if str(row["user_id"]) == str(user_id))
            except (KeyError, TypeError, ValueError):
                return None
            if self._day() != day:
                return None
            if (spent_tenant + reserved_tenant + tokens > self._caps.tenant_tokens_per_day
                    or spent_user + reserved_user + tokens > self._caps.user_tokens_per_day):
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
        """Release after durable completion or a proven pre-provider abort."""
        key = f"llm:pending:v1:{day}"
        for _ in range(16):
            current = self._es.get_setting(tenant_id=str(tenant_id), key=key)
            if not isinstance(current, dict):
                return False
            pending = current.get("pending", {})
            if not isinstance(pending, dict) or request_id not in pending:
                return False
            if self._es.compare_and_set_setting(
                tenant_id=str(tenant_id), key=key, expected=current,
                value={"pending": {rid: row for rid, row in pending.items() if rid != request_id}}):
                return True
        return False
