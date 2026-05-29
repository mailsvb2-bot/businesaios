from __future__ import annotations

"""User state projection helpers for SqliteEventStore.

Incrementally maintains a realtime per-user state snapshot
on every append. Read via get_user_state().
Extracted from sqlite_event_store.py.
"""

import json
import sqlite3
from typing import Any, Dict

from observability.platform.observability.silent import swallow


def get_user_state(
    db: sqlite3.Connection,
    *,
    tenant_id: str = "default",
    user_id: str,
) -> dict[str, Any]:
    try:
        row = db.execute(
            "SELECT state_json, updated_at_ms FROM user_state WHERE tenant_id=? AND user_id=?",
            (str(tenant_id or "default"), str(user_id)),
        ).fetchone()
        if not row:
            return {}
        state = json.loads(row[0]) if row[0] else {}
        if isinstance(state, dict):
            state["_updated_at_ms"] = int(row[1] or 0)
            return state
    except Exception:
        return {}
    return {}


def project_user_state(
    db: sqlite3.Connection,
    *,
    tenant_id: str,
    user_id: str,
    event_type: str,
    ts: int,
    payload_obj: dict[str, Any],
) -> None:
    """Incrementally update user_state for this event (best-effort, never raises)."""
    if user_id in (None, "", "system"):
        return
    try:
        cur = db.execute(
            "SELECT state_json FROM user_state WHERE tenant_id=? AND user_id=?",
            (str(tenant_id or "default"), str(user_id)),
        ).fetchone()
        state: dict[str, Any] = {}
        if cur and cur[0]:
            try:
                state = json.loads(cur[0]) or {}
            except Exception:
                state = {}
        if not isinstance(state, dict):
            state = {}

        state["last_seen_ms"] = int(ts)
        state["last_event_type"] = str(event_type)

        counters = state.get("counters") if isinstance(state.get("counters"), dict) else {}
        counters[str(event_type)] = int(counters.get(str(event_type), 0)) + 1
        state["counters"] = counters

        if str(event_type) == "mood_logged":
            try:
                mood = payload_obj.get("mood")
                if mood is not None:
                    state["mood_last"] = float(mood)
            except Exception:
                swallow(__name__, "sqlite_user_state.mood")

        if str(event_type) in {"payment_created", "payment_succeeded", "payment_failed", "payment_captured"}:
            try:
                state["payment_last_status"] = str(event_type)
            except Exception:
                swallow(__name__, "sqlite_user_state.payment_status")

        if str(event_type) == "tariff_selected":
            try:
                state["selected_plan_id"] = int(payload_obj.get("plan_id") or 0)
                amt = payload_obj.get("amount")
                if amt is not None:
                    state["selected_amount_rub"] = int(amt)
            except Exception:
                swallow(__name__, "sqlite_user_state.tariff")

        db.execute(
            "INSERT INTO user_state(tenant_id,user_id,state_json,updated_at_ms) VALUES (?,?,?,?) "
            "ON CONFLICT(tenant_id,user_id) DO UPDATE SET state_json=excluded.state_json, updated_at_ms=excluded.updated_at_ms",
            (str(tenant_id or "default"), str(user_id), json.dumps(state, ensure_ascii=False, sort_keys=True), int(ts)),
        )
    except Exception:
        return


def delete_user_events(
    db: sqlite3.Connection,
    *,
    tenant_id: str,
    user_id: str,
) -> int:
    """Delete all events for a user within a tenant. Irreversible."""
    tid = str(tenant_id or "").strip()
    uid = str(user_id or "").strip()
    if not tid:
        raise ValueError("tenant_id is required (strict)")
    if not uid:
        raise ValueError("user_id is required (strict)")
    row = db.execute("SELECT COUNT(1) FROM events WHERE tenant_id=? AND user_id=?", (tid, uid)).fetchone()
    before = int(row[0] or 0) if row else 0
    db.execute("DELETE FROM events WHERE tenant_id=? AND user_id=?", (tid, uid))
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise RuntimeError("failed to commit tenant/user delete") from exc
    return int(before)
