from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from runtime.platform.event_store.sqlite_event_store import SqliteEventStore
from tools.tenant_scoped_golden_replay import extract_trace, pick_user_and_window, replay_trace


def _sha256_json(obj) -> str:
    s = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def test_tenant_scoped_golden_replay_picks_user_and_window_and_is_tenant_strict(tmp_path: Path):
    db = tmp_path / "events.db"

    # Create a real sqlite event_store trace with two tenants and overlapping user_ids.
    with SqliteEventStore(str(db)) as es:
        # tenant t1
        es.append_event({"tenant_id": "t1", "user_id": "u1", "event_type": "a", "timestamp_ms": 1000, "payload": {"k": 1}})
        es.append_event({"tenant_id": "t1", "user_id": "u1", "event_type": "b", "timestamp_ms": 2000, "payload": {"k": 2}})
        es.append_event({"tenant_id": "t1", "user_id": "u2", "event_type": "c", "timestamp_ms": 3000, "payload": {"k": 3}})
        # tenant t2 (same user_id as in t1, but must never leak)
        es.append_event({"tenant_id": "t2", "user_id": "u2", "event_type": "x", "timestamp_ms": 4000, "payload": {"k": 9}})
        es.commit()

    spec = pick_user_and_window(db_path=str(db), tenant_id="t1", window_ms=1500, max_users=10, event_limit=200)
    # Most recent user for tenant t1 is u2 @ 3000.
    assert spec.user_id == "u2"
    assert spec.end_ms == 3000
    assert spec.start_ms == 1500

    trace = extract_trace(db_path=str(db), spec=spec)
    assert trace, "trace must not be empty"
    # Tenant strictness: must not include any other tenant.
    assert all(e.get("tenant_id") == "t1" for e in trace)
    assert all(e.get("user_id") == "u2" for e in trace)
    assert [e.get("event_type") for e in trace] == ["c"]

    snap1 = replay_trace(trace=trace, tenant_id="t1", product={}, safe_mode=False)
    snap2 = replay_trace(trace=trace, tenant_id="t1", product={}, safe_mode=False)
    assert snap1 == snap2
    h = _sha256_json(snap1)
    assert h == _sha256_json(snap2)

    # Freeze/verify golden snapshot hash (regression detector).
    golden_file = Path(__file__).resolve().parent / "golden" / "tenant_scoped_golden.json"
    case_name = "synthetic_sqlite_tenant_scoped_v1"
    data = json.loads(golden_file.read_text(encoding="utf-8"))
    assert int(data.get("schema_version") or 0) == 1
    cases = data.get("cases") if isinstance(data.get("cases"), dict) else {}
    assert case_name in cases, f"missing golden case {case_name!r} in {golden_file}"

    if str(os.getenv("GOLDEN_FREEZE") or "").strip().lower() in {"1", "true", "yes", "on"}:
        cases[case_name]["snapshot_sha256"] = h
        golden_file.write_text(
            json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        expected = str(cases[case_name].get("snapshot_sha256") or "")
        assert expected and expected != "__TO_BE_FILLED__", (
            "golden hash is not frozen. Run: GOLDEN_FREEZE=1 pytest -q "
            "tests/test_tenant_scoped_golden_replay_sqlite.py"
        )
        assert h == expected
