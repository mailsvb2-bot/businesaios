from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from typing import Any

from runtime.platform.outbox.sqlite_pragmas import configure_sqlite, is_prod_env

STAGES = ("router", "decide_total", "execute_total", "telegram_api")


def open_ro(path: str) -> sqlite3.Connection:
    uri = f"file:{path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5.0, check_same_thread=False)
    configure_sqlite(conn, prod=is_prod_env())
    return conn


def percentile(sorted_vals: list[int], p: float) -> int:
    if not sorted_vals:
        return 0
    if p <= 0:
        return int(sorted_vals[0])
    if p >= 100:
        return int(sorted_vals[-1])
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return int(sorted_vals[f])
    d0 = sorted_vals[f] * (c - k)
    d1 = sorted_vals[c] * (k - f)
    return int(round(d0 + d1))


@dataclass
class Interaction:
    correlation_key: str
    label: str
    totals: dict[str, int]
    tenant_id: str = "legacy"


def guess_label_from_snapshot_bytes(snapshot_bytes: bytes) -> str:
    try:
        obj = json.loads(snapshot_bytes.decode("utf-8"))
    except Exception:
        return "unknown"

    session = obj.get("session") if isinstance(obj, dict) else None
    if not isinstance(session, dict):
        return "unknown"

    is_cb = bool(session.get("is_callback"))
    cb = session.get("callback_data")
    cmd = session.get("command")
    text = session.get("text")

    if is_cb and isinstance(cb, str) and cb.strip():
        return f"cb:{cb.strip()}"
    if isinstance(cmd, str) and cmd.strip() and cmd.strip() != "/start":
        return f"cmd:{cmd.strip()}"
    if isinstance(text, str) and text.strip():
        t = text.strip().replace("\n", " ")
        if len(t) > 40:
            t = t[:37] + "..."
        return f"text:{t}"
    return "unknown"


def load_interactions(
    *,
    events_db: str,
    snapshots_db: str,
    since_ms: int | None = None,
    tenant_id: str | None = None,
) -> list[Interaction]:
    """Load latency interactions without crossing tenant boundaries.

    ``tenant_id=None`` preserves the historical all-tenant report, but each
    correlation key remains isolated by tenant. Supplying a tenant id scopes
    both decision and latency reads fail-closed to that tenant.
    """
    tenant_scope = str(tenant_id or "").strip() or None
    since = None if since_ms is None else int(since_ms)
    tenant_ck_to_snapshot: dict[tuple[str, str], str] = {}

    with open_ro(events_db) as db:
        clauses = ["event_type='decision_issued'"]
        params: list[Any] = []
        if since is not None:
            clauses.append("timestamp_ms>=?")
            params.append(since)
        if tenant_scope is not None:
            clauses.append("tenant_id=?")
            params.append(tenant_scope)
        q = "SELECT tenant_id, payload_json FROM events WHERE " + " AND ".join(clauses)
        for raw_tenant, payload_json in db.execute(q, tuple(params)).fetchall():
            try:
                payload = json.loads(payload_json) if payload_json else {}
            except Exception:
                payload = {}
            if not isinstance(payload, dict):
                continue
            ck = payload.get("correlation_key")
            sid = payload.get("snapshot_id")
            tid = str(raw_tenant or "legacy").strip() or "legacy"
            if isinstance(ck, str) and ck.strip() and isinstance(sid, str) and sid.strip():
                tenant_ck_to_snapshot.setdefault((tid, ck.strip()), sid.strip())

    tenant_ck_to_label: dict[tuple[str, str], str] = {}
    with open_ro(snapshots_db) as sdb:
        for tenant_ck, sid in list(tenant_ck_to_snapshot.items()):
            row = sdb.execute(
                "SELECT canonical_bytes FROM snapshots WHERE snapshot_id=?",
                (sid,),
            ).fetchone()
            if not row or row[0] is None:
                continue
            tenant_ck_to_label[tenant_ck] = guess_label_from_snapshot_bytes(row[0])

    per_tenant_ck: dict[tuple[str, str], dict[str, list[int]]] = {}
    with open_ro(events_db) as db:
        clauses = ["event_type='latency_span'"]
        params = []
        if since is not None:
            clauses.append("timestamp_ms>=?")
            params.append(since)
        if tenant_scope is not None:
            clauses.append("tenant_id=?")
            params.append(tenant_scope)
        q = "SELECT tenant_id, payload_json FROM events WHERE " + " AND ".join(clauses)
        for raw_tenant, payload_json in db.execute(q, tuple(params)).fetchall():
            try:
                payload = json.loads(payload_json) if payload_json else {}
            except Exception:
                payload = {}
            if not isinstance(payload, dict):
                continue
            stage = payload.get("stage")
            dur = payload.get("duration_ms")
            ck = payload.get("correlation_key")
            if isinstance(dur, bool) or not isinstance(dur, int) or dur < 0:
                continue
            if not (isinstance(stage, str) and isinstance(ck, str) and ck.strip()):
                continue
            if stage not in STAGES:
                continue
            tid = str(raw_tenant or "legacy").strip() or "legacy"
            key = (tid, ck.strip())
            per_tenant_ck.setdefault(key, {}).setdefault(stage, []).append(dur)

    interactions: list[Interaction] = []
    for (tid, ck), stages in per_tenant_ck.items():
        label = tenant_ck_to_label.get((tid, ck), "unknown")
        totals = {st: int(sum(stages.get(st) or [])) for st in STAGES}
        interactions.append(
            Interaction(
                correlation_key=ck,
                label=label,
                totals=totals,
                tenant_id=tid,
            )
        )
    return interactions


def render_report(*, interactions: list[Interaction], top_n: int = 15) -> str:
    by_label: dict[str, list[Interaction]] = {}
    for it in interactions:
        by_label.setdefault(it.label, []).append(it)

    rows = []
    for label, its in by_label.items():
        totals = [sum(i.totals.get(st, 0) for st in STAGES) for i in its]
        totals.sort()
        p50 = percentile(totals, 50)
        p90 = percentile(totals, 90)
        p99 = percentile(totals, 99)

        stage_p90: dict[str, int] = {}
        for st in STAGES:
            vals = sorted([i.totals.get(st, 0) for i in its])
            stage_p90[st] = percentile(vals, 90)
        culprit = max(stage_p90.items(), key=lambda kv: kv[1])[0]
        rows.append((p90, label, p50, p90, p99, culprit, stage_p90))

    rows.sort(key=lambda r: r[0], reverse=True)
    rows = rows[: max(1, int(top_n))]

    out_lines = []
    out_lines.append("TOP buttons by latency (ms) | total = router+decide+execute+telegram")
    out_lines.append("-")
    hdr = f"{'#':>2}  {'button':<32}  {'p50':>5} {'p90':>5} {'p99':>5}  {'culprit':<12}  split_p90(router/decide/execute/tg)"
    out_lines.append(hdr)
    out_lines.append("-" * len(hdr))

    for i, (_, label, p50, p90, p99, culprit, stage_p90) in enumerate(rows, start=1):
        b = label
        if len(b) > 32:
            b = b[:29] + "..."
        split = f"{stage_p90['router']}/{stage_p90['decide_total']}/{stage_p90['execute_total']}/{stage_p90['telegram_api']}"
        out_lines.append(f"{i:>2}  {b:<32}  {p50:>5} {p90:>5} {p99:>5}  {culprit:<12}  {split}")

    return "\n".join(out_lines)


def default_paths_from_env(data_dir: str | None = None) -> tuple[str, str]:
    dd = (data_dir or os.getenv("DATA_DIR") or os.path.join("runtime", "entrypoints", "data")).strip()
    return os.path.join(dd, "events.db"), os.path.join(dd, "snapshots.db")
