from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from core.behavior.behavioral_state_builder import BehavioralStateBuilder
from runtime.platform.event_store.sqlite_event_store import SqliteEventStore
from runtime.tenancy import normalize_tenant_id
from runtime.platform.config.env_flags import env_str


def _normalize_event(e: Dict[str, Any]) -> Dict[str, Any]:
    # Ensure stable keys and shapes for replay.
    return {
        "event_type": str(e.get("event_type") or ""),
        "timestamp_ms": int(e.get("timestamp_ms") or 0),
        "payload": e.get("payload") if isinstance(e.get("payload"), dict) else {},
        "source": str(e.get("source") or ""),
        "user_id": str(e.get("user_id") or ""),
        "tenant_id": str(e.get("tenant_id") or ""),
    }


def _sha256_json(obj: Any) -> str:
    s = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _load_golden(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {"schema_version": 1, "cases": {}}
    if int(data.get("schema_version") or 0) != 1:
        raise SystemExit(f"[TENANT_SCOPED_GOLDEN] unsupported golden schema_version in {path!r}")
    if not isinstance(data.get("cases"), dict):
        data["cases"] = {}
    return data


def _write_golden(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, sort_keys=True, indent=2)
        f.write("\n")


@dataclass(frozen=True)
class TenantScopedReplaySpec:
    tenant_id: str
    user_id: str
    start_ms: int
    end_ms: int
    window_ms: int
    event_limit: int


def pick_user_and_window(
    *,
    db_path: str,
    tenant_id: str,
    window_ms: int,
    max_users: int = 50,
    event_limit: int = 200,
) -> TenantScopedReplaySpec:
    """Pick a user_id for a tenant and a short time window (since_ts).

    Deterministic selection:
    - choose the most recently active user in the tenant (tie-breaker user_id ASC)
    - end_ms = that user's last_ts
    - start_ms = max(0, end_ms - window_ms)
    """
    tid = normalize_tenant_id(tenant_id)
    if not tid:
        raise SystemExit("[TENANT_SCOPED_GOLDEN] tenant_id is required")
    w = max(1, int(window_ms))
    event_limit = max(1, min(int(event_limit), 5000))
    max_users = max(1, min(int(max_users), 1000))

    with SqliteEventStore(str(db_path)) as es:
        candidates: List[Tuple[str, int]] = es.recent_user_ids(tenant_id=tid, start_ms=0, end_ms=None, limit=max_users)
    if not candidates:
        raise SystemExit(f"[TENANT_SCOPED_GOLDEN] no users found for tenant_id={tid!r}")

    user_id, last_ts = candidates[0]
    end_ms = int(last_ts)
    start_ms = max(0, end_ms - w)

    return TenantScopedReplaySpec(
        tenant_id=tid,
        user_id=str(user_id),
        start_ms=int(start_ms),
        end_ms=int(end_ms),
        window_ms=w,
        event_limit=event_limit,
    )


def extract_trace(
    *,
    db_path: str,
    spec: TenantScopedReplaySpec,
) -> List[Dict[str, Any]]:
    trace: List[Dict[str, Any]] = []
    with SqliteEventStore(str(db_path)) as es:
        for ev in es.iter_events(
            tenant_id=str(spec.tenant_id),
            user_id=str(spec.user_id),
            start_ms=int(spec.start_ms),
            end_ms=int(spec.end_ms),
        ):
            trace.append(_normalize_event(ev))

    trace = sorted(trace, key=lambda x: int(x.get("timestamp_ms") or 0))
    if spec.event_limit and len(trace) > int(spec.event_limit):
        trace = trace[-int(spec.event_limit) :]
    return trace


def replay_trace(
    *,
    trace: List[Dict[str, Any]],
    tenant_id: str,
    product: Optional[Dict[str, Any]] = None,
    safe_mode: bool = False,
) -> Dict[str, Any]:
    b = BehavioralStateBuilder()
    return dict(b.build(trace, product=product or {}, tenant_id=str(tenant_id), safe_mode=bool(safe_mode)))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="Path to sqlite events db")
    ap.add_argument("--tenant", default=env_str("TENANT_ID", "default"))
    ap.add_argument("--window-ms", type=int, default=15 * 60 * 1000)
    ap.add_argument("--max-users", type=int, default=50)
    ap.add_argument("--event-limit", type=int, default=200)
    ap.add_argument("--out-trace", default="artifacts/tenant_scoped_golden_trace.json")
    ap.add_argument("--out-snapshot", default="artifacts/tenant_scoped_golden_snapshot.json")
    ap.add_argument("--out-meta", default="artifacts/tenant_scoped_golden_meta.json")
    ap.add_argument("--out-hash", default="artifacts/tenant_scoped_golden_snapshot.sha256")
    ap.add_argument("--safe-mode", action="store_true")
    ap.add_argument("--freeze-golden", action="store_true", help="Write snapshot hash into golden json")
    ap.add_argument(
        "--golden-file",
        default="tests/golden/tenant_scoped_golden.json",
        help="Path to golden json file",
    )
    ap.add_argument("--golden-case", default="tenant_scoped_live_v1", help="Case name in golden json")
    args = ap.parse_args()

    spec = pick_user_and_window(
        db_path=args.db,
        tenant_id=args.tenant,
        window_ms=int(args.window_ms),
        max_users=int(args.max_users),
        event_limit=int(args.event_limit),
    )
    trace = extract_trace(db_path=args.db, spec=spec)
    snap = replay_trace(trace=trace, tenant_id=spec.tenant_id, product={}, safe_mode=bool(args.safe_mode))
    snap_hash = _sha256_json(snap)

    meta = {
        "tenant_id": spec.tenant_id,
        "user_id": spec.user_id,
        "start_ms": spec.start_ms,
        "end_ms": spec.end_ms,
        "window_ms": spec.window_ms,
        "event_limit": spec.event_limit,
        "event_count": len(trace),
        "snapshot_sha256": snap_hash,
        "safe_mode": bool(args.safe_mode),
    }

    os.makedirs(os.path.dirname(args.out_trace) or ".", exist_ok=True)
    with open(args.out_trace, "w", encoding="utf-8") as f:
        json.dump(trace, f, ensure_ascii=False, sort_keys=True, indent=2)
    with open(args.out_snapshot, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, sort_keys=True, indent=2)
    with open(args.out_meta, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, sort_keys=True, indent=2)
    with open(args.out_hash, "w", encoding="utf-8") as f:
        f.write(snap_hash + "\n")

    if bool(args.freeze_golden):
        data = _load_golden(str(args.golden_file))
        cases = data.get("cases")
        assert isinstance(cases, dict)
        cases[str(args.golden_case)] = {
            "snapshot_sha256": snap_hash,
            "meta": {
                "tenant_id": spec.tenant_id,
                "user_id": spec.user_id,
                "start_ms": spec.start_ms,
                "end_ms": spec.end_ms,
                "window_ms": spec.window_ms,
                "event_limit": spec.event_limit,
                "event_count": len(trace),
                "safe_mode": bool(args.safe_mode),
            },
        }
        _write_golden(str(args.golden_file), data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
