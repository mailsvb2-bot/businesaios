from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from threading import RLock


class _MemoryStoredEvent(dict):
    def __init__(self, event: dict, *, append_seq: int) -> None:
        super().__init__(event)
        self.append_seq = int(append_seq)
class MemoryEventStore(list):
    """Append-only in-memory event store for dev/tests.
    Strict tenant contract:
    - caller must pass tenant_id explicitly
    - events are filtered by tenant_id
    - append sequences never move backwards after retention
    """
    def __init__(self, rows: Iterable[dict] = ()) -> None:
        super().__init__()
        self._next_append_seq = 0
        self._settings_lock = RLock()
        self.extend(rows)
    def append(self, event: dict) -> None:
        self._next_append_seq += 1
        super().append(
            _MemoryStoredEvent(
                dict(event or {}),
                append_seq=self._next_append_seq,
            )
        )
    def extend(self, rows: Iterable[dict]) -> None:
        for row in rows:
            self.append(row)
    def append_event(self, event: dict):
        e = dict(event or {})
        tid = str(e.get("tenant_id") or "").strip()
        if not tid:
            raise ValueError("tenant_id is required (strict)")
        self.append(e)
    def latest_append_seq(self, *, tenant_id: str) -> int:
        tid = str(tenant_id or "").strip()
        if not tid:
            raise ValueError("tenant_id is required (strict)")
        return max(
            (
                int(getattr(event, "append_seq", 0))
                for event in self
                if str(event.get("tenant_id") or "") == tid
            ),
            default=0,
        )
    def iter_events(
        self,
        *,
        tenant_id: str,
        start_ms: int = 0,
        end_ms: int | None = None,
        after_append_seq: int | None = None,
        user_id: str | None = None,
        decision_id: str | None = None,
        event_type: str | None = None,
        event_types=None,
        limit: int | None = None,
    ):
        tid = str(tenant_id or "").strip()
        if not tid:
            raise ValueError("tenant_id is required (strict)")
        end_ms = int(end_ms) if end_ms is not None else 2**63 - 1
        start_ms = int(start_ms)
        after = max(0, int(after_append_seq or 0))
        allowed = {str(item) for item in (event_types or ()) if str(item)}
        emitted = 0
        for event in list(self):
            append_seq = int(getattr(event, "append_seq", 0))
            if append_seq <= after:
                continue
            e = dict(event)
            if str(e.get("tenant_id") or "") != tid:
                continue
            ts = int(e.get("timestamp_ms") or 0)
            if ts < start_ms or ts >= end_ms:
                continue
            if user_id is not None and str(e.get("user_id") or "") != str(user_id):
                continue
            if decision_id is not None and str(e.get("decision_id") or "") != str(decision_id):
                continue
            et = e.get("event_type") or e.get("type")
            if event_type and et != event_type:
                continue
            if allowed and str(et or "") not in allowed:
                continue
            if after_append_seq is not None:
                e["append_seq"] = append_seq
            yield e
            emitted += 1
            if limit is not None and emitted >= max(1, int(limit)):
                return
    def count_events(
        self,
        *,
        tenant_id: str,
        start_ms: int = 0,
        end_ms: int | None = None,
        user_id: str | None = None,
        event_type: str | None = None,
    ) -> int:
        return sum(1 for _ in self.iter_events(tenant_id=tenant_id, start_ms=start_ms, end_ms=end_ms, user_id=user_id, event_type=event_type))
    def sum_event_payload_int(
        self,
        *,
        tenant_id: str,
        event_type: str,
        field: str,
        start_ms: int = 0,
        end_ms: int | None = None,
        user_id: str | None = None,
    ) -> int:
        total = 0
        for e in self.iter_events(tenant_id=tenant_id, start_ms=start_ms, end_ms=end_ms, user_id=user_id, event_type=event_type):
            try:
                payload = e.get("payload") or {}
                total += int(payload.get(field) or 0)
            except Exception:
                continue
        return int(total)
    def delete_user_events(self, *, tenant_id: str, user_id: str) -> int:
        """Delete all events for a user without renumbering retained rows."""
        tid = str(tenant_id or "").strip()
        uid = str(user_id or "").strip()
        if not tid:
            raise ValueError("tenant_id is required (strict)")
        if not uid:
            raise ValueError("user_id is required (strict)")
        before = len(self)
        kept = []
        for e in list(self):
            if str(e.get("tenant_id") or "") != tid:
                kept.append(e)
                continue
            if str(e.get("user_id") or "") == uid:
                continue
            kept.append(e)
        super().clear()
        super().extend(kept)
        return int(before - len(self))
    def get_setting(self, *, tenant_id: str, key: str):
        with self._settings_lock:
            store = getattr(self, "_settings", None)
            if store is None:
                return None
            return deepcopy(store.get((str(tenant_id), str(key))))
    def set_setting(self, *, tenant_id: str, key: str, value) -> None:
        with self._settings_lock:
            store = getattr(self, "_settings", None)
            if store is None:
                store = {}
                self._settings = store
            store[(str(tenant_id), str(key))] = deepcopy(value)
    def compare_and_set_setting(self, *, tenant_id: str, key: str, expected, value) -> bool:
        with self._settings_lock:
            store = getattr(self, "_settings", None)
            if store is None:
                store = {}
                self._settings = store
            slot = (str(tenant_id), str(key))
            if store.get(slot) != expected:
                return False
            store[slot] = deepcopy(value)
            return True
