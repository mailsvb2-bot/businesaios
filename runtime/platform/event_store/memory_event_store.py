from __future__ import annotations

class MemoryEventStore(list):
    """Append-only in-memory event store for dev/tests.

    Strict tenant contract:
    - caller must pass tenant_id explicitly
    - events are filtered by tenant_id
    """

    def append_event(self, event: dict):
        e = dict(event or {})
        tid = str(e.get("tenant_id") or "").strip()
        if not tid:
            raise ValueError("tenant_id is required (strict)")
        self.append(e)

    def iter_events(
        self,
        *,
        tenant_id: str,
        start_ms: int = 0,
        end_ms: int | None = None,
        user_id: str | None = None,
        event_type: str | None = None,
    ):
        tid = str(tenant_id or "").strip()
        if not tid:
            raise ValueError("tenant_id is required (strict)")
        end_ms = int(end_ms) if end_ms is not None else 2**63 - 1
        start_ms = int(start_ms)
        for e in list(self):
            if str(e.get("tenant_id") or "") != tid:
                continue
            ts = int(e.get("timestamp_ms") or 0)
            if ts < start_ms or ts >= end_ms:
                continue
            if user_id is not None and str(e.get("user_id") or "") != str(user_id):
                continue
            et = e.get("event_type") or e.get("type")
            if event_type and et != event_type:
                continue
            yield e

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
        """Delete all events for a user within a tenant (in-memory)."""
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
        self.clear()
        self.extend(kept)
        return int(before - len(self))


    def get_setting(self, *, tenant_id: str, key: str):
        store = getattr(self, "_settings", None)
        if store is None:
            return None
        value = store.get((str(tenant_id), str(key)))
        from copy import deepcopy
        return deepcopy(value)

    def set_setting(self, *, tenant_id: str, key: str, value) -> None:
        store = getattr(self, "_settings", None)
        if store is None:
            store = {}
            setattr(self, "_settings", store)
        from copy import deepcopy
        store[(str(tenant_id), str(key))] = deepcopy(value)
