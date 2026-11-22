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
        # Per-tenant policy caps remain authoritative unless explicitly overridden.
        for period in ("week", "month"):
            for subject in ("tenant", "user"):
                name = f"{subject}_tokens_per_{period}"
                if getattr(self, name) is None and getattr(self.policy, name) is not None:
                    object.__setattr__(self, name, getattr(self.policy, name))
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

def _utc_period_bounds_ms(period: str, *, day: str | None = None) -> tuple[int, int]:
    """Calculate all UTC windows against one admission day, not a moving clock."""
    if day is None:
        start, end = _utc_day_bounds_ms()
        today = datetime.fromtimestamp(start / 1000, tz=UTC)
    else:
        parsed = date.fromisoformat(day)
        if parsed.isoformat() != day:
            raise ValueError("LLM_BUDGET_INVALID_DAY")
        today = datetime.combine(parsed, datetime.min.time(), tzinfo=UTC)
        end = int((today + timedelta(days=1)).timestamp() * 1000)
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

    def _sum(self, *, tenant_id: str, user_id: str, period: str = "day", day: str | None = None) -> tuple[int, int]:
        start_ms, end_ms = _utc_period_bounds_ms(period, day=day or self._day())
        if not callable(it := getattr(self._es, "iter_events", None)):
            raise RuntimeError("LLM_BUDGET_EVENT_AGGREGATOR_UNAVAILABLE")
        tenant = user = 0
        for event in it(tenant_id=str(tenant_id), start_ms=start_ms, end_ms=end_ms, event_type=LLM_COMPLETED):
            if (fact := validated_llm_completion_event(event)) is None:
                raise RuntimeError("LLM_BUDGET_CORRUPT_COMPLETION")
            tenant, user = tenant + fact[2][2], user + (fact[2][2] if fact[0] == str(user_id) else 0)
        return tenant, user

    def can_spend(self, *, tenant_id: str, user_id: str, tokens: int) -> bool:
        """Advisory only: reserve is the authoritative CAS admission."""
        if type(tokens) is not int or tokens <= 0:
            return False
        day = self._day()
        spent = {p: self._sum(tenant_id=tenant_id, user_id=user_id, period=p, day=day)
                 for p, _, _ in self._caps.periods()}
        try:
            current = (self._es.get_setting(tenant_id=str(tenant_id), key="llm:pending:v2")
                       if len(self._caps.periods()) > 1 else None)
            if not isinstance(current, dict | type(None)):
                return False
            if current is not None and (type(current.get("revision", 0)) is not int or current.get("revision", 0) < 0):
                return False
            pending = (current or {}).get("pending", {})
            if not isinstance(pending, dict):
                return False
            claims = self._pending_across_periods(
                tenant_id=tenant_id, user_id=user_id, day=day, pending=pending,
            )
            return all(spent[p][0] + claims[p][0] + tokens <= tc and
                       spent[p][1] + claims[p][1] + tokens <= uc
                       for p, tc, uc in self._caps.periods())
        except RuntimeError as exc:
            if str(exc) not in {"LLM_BUDGET_LEGACY_WRITER_ACTIVE", "LLM_BUDGET_CORRUPT_RESERVATION"}:
                raise
            return False
        except (ValueError, TypeError, KeyError, AttributeError):
            return False

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

    def _reconcile_legacy_window(self, *, tenant_id: str, day: str) -> bool:
        """Only validated durable completions may clear historical v1 holds."""
        oldest = min(_utc_period_bounds_ms(p, day=day)[0] for p, _, _ in self._caps.periods())
        old_day = date.fromisoformat(day)
        changed = False
        while int(datetime.combine(old_day, datetime.min.time(), tzinfo=UTC).timestamp() * 1000) >= oldest:
            old_date = old_day.isoformat()
            existing = self._es.get_setting(tenant_id=str(tenant_id), key=f"llm:pending:v1:{old_date}")
            if isinstance(existing, dict) and isinstance(existing.get("pending"), dict) and existing["pending"]:
                changed = self._reconcile_completed(tenant_id=tenant_id, day=old_date, current=existing) or changed
            old_day -= timedelta(days=1)
        return changed

    def _pending_across_periods(self, *, tenant_id: str, user_id: str, day: str, pending: dict) -> dict[str, tuple[int, int]]:
        """All unresolved claims count within their original UTC budget periods."""
        today = date.fromisoformat(day)
        periods = self._caps.periods()
        oldest = min(_utc_period_bounds_ms(p, day=day)[0] for p, _, _ in periods)
        totals = {p: [0, 0] for p, _, _ in periods}
        # Scan legacy day buckets as well as the tenant-wide CAS bucket.
        entries = [(day, pending)]
        old_day = today
        while int(datetime.combine(old_day, datetime.min.time(), tzinfo=UTC).timestamp() * 1000) >= oldest:
            key = f"llm:pending:v1:{old_day.isoformat()}"
            legacy = self._es.get_setting(tenant_id=str(tenant_id), key=key)
            if legacy is not None:
                if not isinstance(legacy, dict) or not isinstance(legacy.get("pending"), dict):
                    raise RuntimeError("LLM_BUDGET_CORRUPT_RESERVATION")
                if legacy["pending"] and self._es.get_setting(tenant_id=str(tenant_id), key="llm:pending:v2") is not None:
                    raise RuntimeError("LLM_BUDGET_LEGACY_WRITER_ACTIVE")
                entries.append((old_day.isoformat(), legacy["pending"]))
            old_day -= timedelta(days=1)
        for default_day, rows in entries:
            for request_id, row in rows.items():
                if not isinstance(request_id, str) or not request_id or not isinstance(row, dict):
                    raise RuntimeError("LLM_BUDGET_CORRUPT_RESERVATION")
                owner, tokens, when = row.get("user_id"), row.get("tokens"), row.get("day", default_day)
                if not isinstance(owner, str) or not owner.strip() or type(tokens) is not int or tokens <= 0 or not isinstance(when, str):
                    raise RuntimeError("LLM_BUDGET_CORRUPT_RESERVATION")
                try:
                    parsed = date.fromisoformat(when)
                    if parsed.isoformat() != when or parsed > today:
                        raise ValueError("invalid day")
                except ValueError as exc:
                    raise RuntimeError("LLM_BUDGET_CORRUPT_RESERVATION") from exc
                at = int(datetime.combine(parsed, datetime.min.time(), tzinfo=UTC).timestamp() * 1000)
                for period in totals:
                    if at >= _utc_period_bounds_ms(period, day=day)[0]:
                        totals[period][0] += tokens
                        if owner == str(user_id):
                            totals[period][1] += tokens
        return {k: (v[0], v[1]) for k, v in totals.items()}

    @staticmethod
    def _next_v2_state(current: dict | None, pending: dict) -> dict:
        """Advance CAS identity even when the pending set returns to an earlier shape."""
        revision = 0 if current is None else current.get("revision", 0)
        if type(revision) is not int or revision < 0:
            raise ValueError("LLM_BUDGET_CORRUPT_REVISION")
        return {"revision": revision + 1, "pending": pending}

    def _reconcile_v2(self, *, tenant_id: str, current: dict) -> bool:
        pending = current.get("pending")
        if not isinstance(pending, dict) or not pending:
            return False
        try:
            days = [date.fromisoformat(row["day"]) for row in pending.values()]
            earliest = min(days)
            start = int(datetime.combine(earliest, datetime.min.time(), tzinfo=UTC).timestamp() * 1000)
            end = _utc_period_bounds_ms("day", day=self._day())[1]
            completed = set()
            for event in self._es.iter_events(tenant_id=str(tenant_id), start_ms=start, end_ms=end, event_type=LLM_COMPLETED):
                fact = validated_llm_completion_event(event)
                if fact is None:
                    return False
                completed.add(fact[:2])
            remaining = {rid: row for rid, row in pending.items() if (row["user_id"], rid) not in completed}
            return len(remaining) < len(pending) and self._es.compare_and_set_setting(
                tenant_id=str(tenant_id), key="llm:pending:v2", expected=current, value=self._next_v2_state(current, remaining)
            )
        except (TypeError, ValueError, KeyError, AttributeError):
            return False

    def reserve(self, *, tenant_id: str, user_id: str, tokens: int, request_id: str) -> str | None:
        get, cas = getattr(self._es, "get_setting", None), getattr(self._es, "compare_and_set_setting", None)
        if not callable(get) or not callable(cas) or type(tokens) is not int or tokens <= 0 or any(
            not isinstance(v, str) or not v.strip() for v in (tenant_id, user_id, request_id)
        ):
            return None
        periods = self._caps.periods()
        v2 = len(periods) > 1
        admission_day = None if v2 else self._day()
        for _ in range(16):
            day = self._day() if v2 else admission_day
            key = "llm:pending:v2" if v2 else f"llm:pending:v1:{day}"
            current = get(tenant_id=str(tenant_id), key=key)
            if not isinstance(current, dict | type(None)):
                return None
            pending = (current or {}).get("pending", {})
            if not isinstance(pending, dict) or request_id in pending:
                return None
            if v2 and current is not None and (
                type(current.get("revision", 0)) is not int or current.get("revision", 0) < 0
            ):
                return None
            spent = {p: self._sum(tenant_id=tenant_id, user_id=user_id, period=p, day=day)
                     for p, _, _ in periods}
            try:
                holds = self._pending_across_periods(
                    tenant_id=tenant_id, user_id=user_id, day=day, pending=pending if v2 else {},
                )
            except RuntimeError as exc:
                if v2 and str(exc) == "LLM_BUDGET_LEGACY_WRITER_ACTIVE" and self._reconcile_legacy_window(
                    tenant_id=tenant_id, day=day,
                ):
                    continue
                return None
            if self._day() != day:
                if v2:
                    continue
                return None
            exceeds_cap = any(
                spent[p][0] + holds[p][0] + tokens > tc or spent[p][1] + holds[p][1] + tokens > uc
                for p, tc, uc in periods
            )
            if exceeds_cap:
                if v2 and pending and self._reconcile_v2(tenant_id=tenant_id, current=current):
                    continue
                if v2 and self._reconcile_legacy_window(tenant_id=tenant_id, day=day):
                    continue
                if not v2 and current is not None and self._reconcile_completed(
                    tenant_id=tenant_id, day=day, current=current,
                ):
                    continue
                return None
            row = {"user_id": str(user_id), "tokens": tokens}
            if v2:
                row["day"] = day
            next_pending = {**pending, request_id: row}
            state = self._next_v2_state(current, next_pending) if v2 else {"pending": next_pending}
            if cas(tenant_id=str(tenant_id), key=key, expected=current, value=state):
                return self._claim_reservation(
                    tenant_id=tenant_id, user_id=user_id, request_id=request_id, day=day,
                    check_day=v2,
                )
        return None

    def _claim_reservation(self, *, tenant_id: str, user_id: str, request_id: str,
                           day: str, check_day: bool) -> str | None:
        """One-shot claim belongs to the canonical reservation, never an older retry."""
        claimed = False
        try:
            claimed = self._es.compare_and_set_setting(
                tenant_id=str(tenant_id), key=f"llm:claim:v2:{request_id}",
                expected=None, value={"user_id": str(user_id)},
            )
            if claimed and check_day and self._day() != day:
                self.cancel_unstarted_reservation(tenant_id=tenant_id, request_id=request_id, day=day)
                return None
            return day if claimed else None
        finally:
            if not claimed:
                self.release(tenant_id=tenant_id, request_id=request_id, day=day)

    def cancel_unstarted_reservation(self, *, tenant_id: str, request_id: str, day: str) -> bool:
        """Remove only this pre-provider reservation and its matching one-shot claim.

        A failed LLM_REQUESTED journal append must allow a safe retry; a failed
        LLM_COMPLETED append must keep its claim and cannot use this method.
        """
        try:
            for key in ("llm:pending:v2", f"llm:pending:v1:{day}"):
                state = self._es.get_setting(tenant_id=str(tenant_id), key=key)
                pending = state.get("pending") if isinstance(state, dict) else None
                row = pending.get(request_id) if isinstance(pending, dict) else None
                if not isinstance(row, dict):
                    continue
                owner = row.get("user_id")
                if not isinstance(owner, str) or not owner.strip():
                    return False
                if key == "llm:pending:v2" and row.get("day") != day:
                    return False
                if not self.release(tenant_id=tenant_id, request_id=request_id, day=day):
                    return False
                claim_key = f"llm:claim:v2:{request_id}"
                claim = self._es.get_setting(tenant_id=str(tenant_id), key=claim_key)
                if claim is None:
                    return True
                return claim == {"user_id": owner} and bool(self._es.compare_and_set_setting(
                    tenant_id=str(tenant_id), key=claim_key, expected=claim, value=None,
                ))
            return False
        except Exception:  # noqa: BLE001
            return False

    def release(self, *, tenant_id: str, request_id: str, day: str) -> bool:
        # Preserve legacy v1 cancellation for already reserved provider calls.
        for key in ("llm:pending:v2", f"llm:pending:v1:{day}"):
            for _ in range(16):
                current = self._es.get_setting(tenant_id=str(tenant_id), key=key)
                if not isinstance(current, dict):
                    break
                pending = current.get("pending", {})
                if not isinstance(pending, dict):
                    return False
                if request_id not in pending:
                    break
                if key == "llm:pending:v2" and pending[request_id].get("day") != day:
                    return False
                remaining = {rid: row for rid, row in pending.items() if rid != request_id}
                value = self._next_v2_state(current, remaining) if key == "llm:pending:v2" else {"pending": remaining}
                if self._es.compare_and_set_setting(tenant_id=str(tenant_id), key=key, expected=current, value=value):
                    return True
        return False
