from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.behavior.behavioral_state_builder import BehavioralStateBuilder
from runtime.platform.config.env_flags import env_str
from runtime.platform.event_store.sqlite_event_store import SqliteEventStore
from runtime.tenancy import normalize_tenant_id


def _normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    # Ensure stable keys and shapes for replay.
    return {
        "event_type": str(event.get("event_type") or ""),
        "timestamp_ms": int(event.get("timestamp_ms") or 0),
        "payload": event.get("payload") if isinstance(event.get("payload"), dict) else {},
        "source": str(event.get("source") or ""),
        "user_id": str(event.get("user_id") or ""),
        "tenant_id": str(event.get("tenant_id") or ""),
    }


def _sha256_json(obj: Any) -> str:
    payload = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_golden(path: str) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {"schema_version": 1, "cases": {}}
    if int(data.get("schema_version") or 0) != 1:
        raise SystemExit(f"[TENANT_SCOPED_GOLDEN] unsupported golden schema_version in {path!r}")
    if not isinstance(data.get("cases"), dict):
        data["cases"] = {}
    return data


def _write_golden(path: str, data: dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


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
    window = max(1, int(window_ms))
    event_limit = max(1, min(int(event_limit), 5000))
    max_users = max(1, min(int(max_users), 1000))

    with SqliteEventStore(str(db_path)) as event_store:
        candidates: list[tuple[str, int]] = event_store.recent_user_ids(
            tenant_id=tid,
            start_ms=0,
            end_ms=None,
            limit=max_users,
        )
    if not candidates:
        raise SystemExit(f"[TENANT_SCOPED_GOLDEN] no users found for tenant_id={tid!r}")

    user_id, last_ts = candidates[0]
    end_ms = int(last_ts)
    start_ms = max(0, end_ms - window)

    return TenantScopedReplaySpec(
        tenant_id=tid,
        user_id=str(user_id),
        start_ms=int(start_ms),
        end_ms=int(end_ms),
        window_ms=window,
        event_limit=event_limit,
    )


def extract_trace(
    *,
    db_path: str,
    spec: TenantScopedReplaySpec,
) -> list[dict[str, Any]]:
    trace: list[dict[str, Any]] = []
    with SqliteEventStore(str(db_path)) as event_store:
        for event in event_store.iter_events(
            tenant_id=str(spec.tenant_id),
            user_id=str(spec.user_id),
            start_ms=int(spec.start_ms),
            end_ms=int(spec.end_ms),
        ):
            trace.append(_normalize_event(event))

    trace = sorted(trace, key=lambda item: int(item.get("timestamp_ms") or 0))
    if spec.event_limit and len(trace) > int(spec.event_limit):
        trace = trace[-int(spec.event_limit) :]
    return trace


def replay_trace(
    *,
    trace: list[dict[str, Any]],
    tenant_id: str,
    product: dict[str, Any] | None = None,
    safe_mode: bool = False,
) -> dict[str, Any]:
    builder = BehavioralStateBuilder()
    return dict(builder.build(trace, product=product or {}, tenant_id=str(tenant_id), safe_mode=bool(safe_mode)))


def _write_json(path: str, payload: object) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )


def _write_text(path: str, payload: str) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(payload, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, help="Path to sqlite events db")
    parser.add_argument("--tenant", default=env_str("TENANT_ID", "default"))
    parser.add_argument("--window-ms", type=int, default=15 * 60 * 1000)
    parser.add_argument("--max-users", type=int, default=50)
    parser.add_argument("--event-limit", type=int, default=200)
    parser.add_argument("--out-trace", default="artifacts/tenant_scoped_golden_trace.json")
    parser.add_argument("--out-snapshot", default="artifacts/tenant_scoped_golden_snapshot.json")
    parser.add_argument("--out-meta", default="artifacts/tenant_scoped_golden_meta.json")
    parser.add_argument("--out-hash", default="artifacts/tenant_scoped_golden_snapshot.sha256")
    parser.add_argument("--safe-mode", action="store_true")
    parser.add_argument("--freeze-golden", action="store_true", help="Write snapshot hash into golden json")
    parser.add_argument(
        "--golden-file",
        default="tests/golden/tenant_scoped_golden.json",
        help="Path to golden json file",
    )
    parser.add_argument("--golden-case", default="tenant_scoped_live_v1", help="Case name in golden json")
    args = parser.parse_args()

    spec = pick_user_and_window(
        db_path=args.db,
        tenant_id=args.tenant,
        window_ms=int(args.window_ms),
        max_users=int(args.max_users),
        event_limit=int(args.event_limit),
    )
    trace = extract_trace(db_path=args.db, spec=spec)
    snapshot = replay_trace(trace=trace, tenant_id=spec.tenant_id, product={}, safe_mode=bool(args.safe_mode))
    snapshot_hash = _sha256_json(snapshot)

    meta = {
        "tenant_id": spec.tenant_id,
        "user_id": spec.user_id,
        "start_ms": spec.start_ms,
        "end_ms": spec.end_ms,
        "window_ms": spec.window_ms,
        "event_limit": spec.event_limit,
        "event_count": len(trace),
        "snapshot_sha256": snapshot_hash,
        "safe_mode": bool(args.safe_mode),
    }

    _write_json(args.out_trace, trace)
    _write_json(args.out_snapshot, snapshot)
    _write_json(args.out_meta, meta)
    _write_text(args.out_hash, snapshot_hash + "\n")

    if bool(args.freeze_golden):
        data = _load_golden(str(args.golden_file))
        cases = data.get("cases")
        assert isinstance(cases, dict)
        cases[str(args.golden_case)] = {
            "snapshot_sha256": snapshot_hash,
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
