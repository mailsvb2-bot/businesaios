from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol

from config.llm_budget_policy import DEFAULT_LLM_BUDGET_POLICY, LLMBudgetPolicy
from core.telemetry.event_types import LLM_COMPLETED
from core.telemetry.trace_utils import day_key_utc


_PENDING_STATE_KEY = "llm:pending:v2"
_UNSET = object()


@dataclass(frozen=True)
class BudgetCaps:
    policy: LLMBudgetPolicy = field(default_factory=lambda: DEFAULT_LLM_BUDGET_POLICY)
    tenant_tokens_per_day: int | None = None
    user_tokens_per_day: int | None = None
    tenant_tokens_per_week: int | None = None
    user_tokens_per_week: int | None = None
    tenant_tokens_per_month: int | None = None
    user_tokens_per_month: int | None = None

    def __post_init__(self) -> None:
        tenant_day_overridden = self.tenant_tokens_per_day is not None
        user_day_overridden = self.user_tokens_per_day is not None
        tenant_day = self.policy.tenant_tokens_per_day if self.tenant_tokens_per_day is None else self.tenant_tokens_per_day
        user_day = self.policy.user_tokens_per_day if self.user_tokens_per_day is None else self.user_tokens_per_day
        values = {
            "tenant_tokens_per_day": tenant_day,
            "user_tokens_per_day": user_day,
            "tenant_tokens_per_week": (
                self.policy.tenant_tokens_per_week if self.tenant_tokens_per_week is None and not tenant_day_overridden
                else tenant_day * 7 if self.tenant_tokens_per_week is None else self.tenant_tokens_per_week
            ),
            "user_tokens_per_week": (
                self.policy.user_tokens_per_week if self.user_tokens_per_week is None and not user_day_overridden
                else user_day * 7 if self.user_tokens_per_week is None else self.user_tokens_per_week
            ),
            "tenant_tokens_per_month": (
                self.policy.tenant_tokens_per_month if self.tenant_tokens_per_month is None and not tenant_day_overridden
                else tenant_day * 30 if self.tenant_tokens_per_month is None else self.tenant_tokens_per_month
            ),
            "user_tokens_per_month": (
                self.policy.user_tokens_per_month if self.user_tokens_per_month is None and not user_day_overridden
                else user_day * 30 if self.user_tokens_per_month is None else self.user_tokens_per_month
            ),
        }
        for name, value in values.items():
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
            object.__setattr__(self, name, value)


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


def estimate_request_tokens(request: Any) -> int:
    return int(request.max_tokens) + 800 + sum(len(m.content.encode("utf-8")) for m in request.messages)


def validated_llm_usage(usage: Any) -> tuple[int, int, int] | None:
    """Validate provider measurements; never substitute a reservation estimate."""
    values = tuple((usage.get(key) if isinstance(usage, Mapping) else getattr(usage, key, None)) for key in ("prompt_tokens", "completion_tokens", "total_tokens"))
    return values if all(type(v) is int and v >= 0 for v in values) and values[2] > 0 and values[2] >= values[0] + values[1] else None


def validated_llm_completion_event(event: Any) -> tuple[str, str, tuple[int, int, int]] | None:
    if not isinstance(event, dict):
        return None
    user, payload = event.get("user_id"), event.get("payload")
    if not isinstance(user, str) or not user.strip() or not isinstance(payload, dict):
        return None
    request_id, provider, model = (payload.get(key) for key in ("request_id", "provider", "model"))
    usage = validated_llm_usage(payload)
    return (user, request_id, usage) if all(isinstance(v, str) and v.strip() for v in (request_id, provider, model)) and usage is not None else None


def has_durable_budget_store(event_store: Any) -> bool:
    return all(callable(getattr(event_store, name, None)) for name in ("iter_events", "get_setting", "compare_and_set_setting", "append_event"))


class EventStoreDailyTokenBudget:
    """Durable token accounting with one tenant-wide atomic reservation state."""

    def __init__(self, *, event_store: Any, caps: BudgetCaps, cache_ttl_s: float = DEFAULT_LLM_BUDGET_POLICY.cache_ttl_seconds) -> None:
        self._es, self._caps = event_store, caps

    def _day(self) -> str:
        return day_key_utc()

    def _period_bounds(self, *, day: str, period: str) -> tuple[date, int, int]:
        try:
            current = date.fromisoformat(day)
            if current.isoformat() != day or period not in {"day", "week", "month"}:
                raise ValueError("invalid budget period")
            start = current if period == "day" else current - timedelta(days=current.weekday()) if period == "week" else current.replace(day=1)
            end = start + timedelta(days=1) if period == "day" else start + timedelta(days=7) if period == "week" else (start.replace(day=28) + timedelta(days=4)).replace(day=1)
            return start, int(datetime.combine(start, datetime.min.time(), tzinfo=UTC).timestamp() * 1000), int(datetime.combine(end, datetime.min.time(), tzinfo=UTC).timestamp() * 1000)
        except (TypeError, ValueError, OverflowError) as exc:
            raise RuntimeError("LLM_BUDGET_PERIOD_INVALID") from exc

    def _period_days(self, *, day: str, period: str) -> tuple[date, ...]:
        start, _start_ms, _end_ms = self._period_bounds(day=day, period=period)
        current = date.fromisoformat(day)
        return tuple(start + timedelta(days=offset) for offset in range((current - start).days + 1))

    def _sum_window(self, *, tenant_id: str, user_id: str, start_ms: int, end_ms: int) -> tuple[int, int]:
        it = getattr(self._es, "iter_events", None)
        if not callable(it):
            raise RuntimeError("LLM_BUDGET_EVENT_AGGREGATOR_UNAVAILABLE")
        tenant = user = 0
        for event in it(tenant_id=str(tenant_id), start_ms=start_ms, end_ms=end_ms, event_type=LLM_COMPLETED):
            validated = validated_llm_completion_event(event)
            if validated is None:
                raise RuntimeError("LLM_BUDGET_CORRUPT_COMPLETION")
            event_user, _request_id, (_prompt, _completion, value) = validated
            tenant += value
            if event_user == str(user_id):
                user += value
        return tenant, user

    def _period_caps(self, period: str) -> tuple[int, int]:
        return {
            "day": (self._caps.tenant_tokens_per_day, self._caps.user_tokens_per_day),
            "week": (self._caps.tenant_tokens_per_week, self._caps.user_tokens_per_week),
            "month": (self._caps.tenant_tokens_per_month, self._caps.user_tokens_per_month),
        }[period]

    def _legacy_pending(self, *, tenant_id: str, day: str) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
        get = getattr(self._es, "get_setting", None)
        if not callable(get):
            raise RuntimeError("LLM_BUDGET_RESERVATION_STORE_UNAVAILABLE")
        days = set(self._period_days(day=day, period="week")) | set(self._period_days(day=day, period="month"))
        pending: dict[str, dict[str, Any]] = {}
        snapshots: dict[str, dict[str, Any]] = {}
        for value in sorted(days):
            key = value.isoformat()
            state = get(tenant_id=str(tenant_id), key=f"llm:pending:v1:{key}")
            if state is None:
                continue
            if not isinstance(state, dict) or not isinstance(state.get("pending"), dict):
                raise RuntimeError("LLM_BUDGET_CORRUPT_RESERVATION")
            snapshots[key] = state
            for request_id, row in state["pending"].items():
                if not isinstance(request_id, str) or not request_id.strip() or not isinstance(row, dict):
                    raise RuntimeError("LLM_BUDGET_CORRUPT_RESERVATION")
                user, tokens = row.get("user_id"), row.get("tokens")
                if not isinstance(user, str) or not user.strip() or type(tokens) is not int or tokens <= 0:
                    raise RuntimeError("LLM_BUDGET_CORRUPT_RESERVATION")
                normalized = {"user_id": user, "tokens": tokens, "day": key}
                if request_id in pending and pending[request_id] != normalized:
                    raise RuntimeError("LLM_BUDGET_DUPLICATE_LEGACY_RESERVATION")
                pending[request_id] = normalized
        return pending, snapshots

    def _pending_state(self, *, tenant_id: str, day: str) -> tuple[Any, dict[str, Any], dict[str, dict[str, Any]]]:
        current = self._es.get_setting(tenant_id=str(tenant_id), key=_PENDING_STATE_KEY)
        legacy, snapshots = self._legacy_pending(tenant_id=tenant_id, day=day)
        if current is None:
            return None, {"revision": 0, "pending": legacy}, snapshots
        if (
            not isinstance(current, dict)
            or type(current.get("revision")) is not int
            or current["revision"] < 0
            or not isinstance(current.get("pending"), dict)
        ):
            raise RuntimeError("LLM_BUDGET_CORRUPT_RESERVATION")
        for request_id, row in legacy.items():
            stored = current["pending"].get(request_id)
            if not isinstance(stored, dict) or any(stored.get(key) != row[key] for key in ("user_id", "tokens", "day")):
                raise RuntimeError("LLM_BUDGET_LEGACY_RESERVATION_UNRECONCILED")
        return current, current, snapshots

    def _clear_legacy(self, *, tenant_id: str, snapshots: Mapping[str, dict[str, Any]]) -> None:
        for day, state in snapshots.items():
            if state.get("pending"):
                self._es.compare_and_set_setting(
                    tenant_id=str(tenant_id), key=f"llm:pending:v1:{day}",
                    expected=state, value={"pending": {}},
                )

    def _pending_totals(self, *, user_id: str, day: str, period: str, state: Any) -> tuple[int, int]:
        if state is None:
            return 0, 0
        if not isinstance(state, dict) or not isinstance(state.get("pending"), dict):
            raise RuntimeError("LLM_BUDGET_CORRUPT_RESERVATION")
        _start, start_ms, end_ms = self._period_bounds(day=day, period=period)
        tenant = user = 0
        for request_id, row in state["pending"].items():
            if not isinstance(request_id, str) or not request_id.strip() or not isinstance(row, dict):
                raise RuntimeError("LLM_BUDGET_CORRUPT_RESERVATION")
            row_user, tokens, row_day = row.get("user_id"), row.get("tokens"), row.get("day")
            if not isinstance(row_user, str) or not row_user.strip() or type(tokens) is not int or tokens <= 0 or not isinstance(row_day, str):
                raise RuntimeError("LLM_BUDGET_CORRUPT_RESERVATION")
            try:
                parsed = date.fromisoformat(row_day)
                stamp = int(datetime.combine(parsed, datetime.min.time(), tzinfo=UTC).timestamp() * 1000)
                if parsed.isoformat() != row_day:
                    raise ValueError("non-canonical reservation day")
            except (TypeError, ValueError, OverflowError) as exc:
                raise RuntimeError("LLM_BUDGET_CORRUPT_RESERVATION") from exc
            if start_ms <= stamp < end_ms:
                tenant += tokens
                user += tokens if row_user == str(user_id) else 0
        return tenant, user

    def _periods_allow(self, *, tenant_id: str, user_id: str, tokens: int, day: str, state: Any) -> bool:
        if type(tokens) is not int or tokens <= 0:
            return False
        for period in ("day", "week", "month"):
            _start, start_ms, end_ms = self._period_bounds(day=day, period=period)
            spent_tenant, spent_user = self._sum_window(tenant_id=tenant_id, user_id=user_id, start_ms=start_ms, end_ms=end_ms)
            reserved_tenant, reserved_user = self._pending_totals(user_id=user_id, day=day, period=period, state=state)
            tenant_cap, user_cap = self._period_caps(period)
            if type(tenant_cap) is not int or tenant_cap <= 0 or type(user_cap) is not int or user_cap <= 0:
                return False
            if spent_tenant + reserved_tenant + tokens > tenant_cap or spent_user + reserved_user + tokens > user_cap:
                return False
        return True

    def _reconcile_completed(
        self, *, tenant_id: str, day: str, current: dict,
        expected_state: Any = _UNSET, legacy_states: Mapping[str, dict[str, Any]] | None = None,
    ) -> bool:
        it = getattr(self._es, "iter_events", None)
        if (
            not callable(it) or not isinstance(current, dict)
            or type(current.get("revision")) is not int or current["revision"] < 0
            or not isinstance(current.get("pending"), dict) or not current["pending"]
        ):
            return False
        try:
            today = date.fromisoformat(day)
            if today.isoformat() != day:
                return False
            week_start = self._period_bounds(day=day, period="week")[0]
            month_start = self._period_bounds(day=day, period="month")[0]
            active_start = min(week_start, month_start)
            relevant = {}
            for request_id, row in current["pending"].items():
                if not isinstance(request_id, str) or not request_id.strip() or not isinstance(row, dict):
                    return False
                user, tokens = row.get("user_id"), row.get("tokens")
                row_day = date.fromisoformat(row.get("day") or day)
                if not isinstance(user, str) or not user.strip() or type(tokens) is not int or tokens <= 0 or row_day > today:
                    return False
                if row_day >= active_start:
                    relevant[request_id] = row
            if not relevant:
                return False
            start_day = min(date.fromisoformat(row.get("day") or day) for row in relevant.values())
            start = int(datetime.combine(start_day, datetime.min.time(), tzinfo=UTC).timestamp() * 1000)
            end = int(datetime.combine(today + timedelta(days=1), datetime.min.time(), tzinfo=UTC).timestamp() * 1000)
        except (TypeError, ValueError, OverflowError):
            return False
        completed = set()
        try:
            for event in it(tenant_id=str(tenant_id), start_ms=start, end_ms=end, event_type=LLM_COMPLETED):
                fact = validated_llm_completion_event(event)
                if fact is None:
                    return False
                completed.add((fact[0], fact[1]))
        except (TypeError, ValueError, AttributeError):
            return False
        remaining = {
            request_id: row for request_id, row in current["pending"].items()
            if request_id not in relevant or (str(row["user_id"]), request_id) not in completed
        }
        if len(remaining) == len(current["pending"]):
            return False
        expected = current if expected_state is _UNSET else expected_state
        if not self._es.compare_and_set_setting(
            tenant_id=str(tenant_id), key=_PENDING_STATE_KEY,
            expected=expected, value={"revision": current["revision"] + 1, "pending": remaining},
        ):
            return False
        self._clear_legacy(tenant_id=tenant_id, snapshots=legacy_states or {})
        return True

    def _sum(self, *, tenant_id: str, user_id: str) -> tuple[int, int]:
        _start, start_ms, end_ms = self._period_bounds(day=self._day(), period="day")
        return self._sum_window(tenant_id=tenant_id, user_id=user_id, start_ms=start_ms, end_ms=end_ms)

    def can_spend(self, *, tenant_id: str, user_id: str, tokens: int) -> bool:
        if type(tokens) is not int or tokens <= 0:
            return False
        day = self._day()
        try:
            _expected, state, _legacy = self._pending_state(tenant_id=tenant_id, day=day)
        except RuntimeError:
            return False
        return self._periods_allow(tenant_id=tenant_id, user_id=user_id, tokens=tokens, day=day, state=state)

    def spend(self, *, tenant_id: str, user_id: str, tokens: int) -> None:
        return None  # Durable completion events are authoritative.

    def reserve(self, *, tenant_id: str, user_id: str, tokens: int, request_id: str) -> str | None:
        """Atomically reserve daily, weekly and monthly headroom in one tenant CAS."""
        get, cas = getattr(self._es, "get_setting", None), getattr(self._es, "compare_and_set_setting", None)
        if not callable(get) or not callable(cas) or type(tokens) is not int or tokens <= 0:
            return None
        if any(not isinstance(value, str) or not value.strip() for value in (tenant_id, user_id, request_id)):
            return None
        day = self._day()
        for _ in range(16):
            try:
                expected, current, legacy = self._pending_state(tenant_id=tenant_id, day=day)
                pending = current["pending"]
                if request_id in pending or self._day() != day:
                    return None
                if not self._periods_allow(tenant_id=tenant_id, user_id=user_id, tokens=tokens, day=day, state=current):
                    if self._reconcile_completed(
                        tenant_id=tenant_id, day=day, current=current,
                        expected_state=expected, legacy_states=legacy,
                    ):
                        continue
                    return None
            except RuntimeError:
                return None
            state = {"revision": current["revision"] + 1, "pending": {**pending, request_id: {"user_id": user_id, "tokens": tokens, "day": day}}}
            if cas(tenant_id=str(tenant_id), key=_PENDING_STATE_KEY, expected=expected, value=state):
                try:
                    self._clear_legacy(tenant_id=tenant_id, snapshots=legacy)
                    self._pending_state(tenant_id=tenant_id, day=day)
                except RuntimeError:
                    self.cancel_unstarted_reservation(tenant_id=tenant_id, request_id=request_id, day=day)
                    return None
                claimed = False
                try:
                    claimed = cas(tenant_id=str(tenant_id), key=f"llm:claim:v2:{request_id}", expected=None, value={"user_id": user_id})
                    if claimed and self._day() != day:
                        cas(tenant_id=str(tenant_id), key=f"llm:claim:v2:{request_id}", expected={"user_id": user_id}, value=None)
                        claimed = False
                        return None
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
        for key in (_PENDING_STATE_KEY, f"llm:pending:v1:{day}"):
            for _ in range(16):
                current = self._es.get_setting(tenant_id=str(tenant_id), key=key)
                if not isinstance(current, dict) or not isinstance(current.get("pending"), dict):
                    break
                pending = current["pending"]
                if request_id not in pending:
                    break
                value = {"pending": {rid: row for rid, row in pending.items() if rid != request_id}}
                if key == _PENDING_STATE_KEY:
                    revision = current.get("revision")
                    if type(revision) is not int or revision < 0:
                        return False
                    value["revision"] = revision + 1
                if self._es.compare_and_set_setting(
                    tenant_id=str(tenant_id), key=key, expected=current, value=value,
                ):
                    return True
        return False
