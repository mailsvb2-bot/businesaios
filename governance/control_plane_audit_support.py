from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from governance.persistence_codec import to_jsonable


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def safe_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def text(value: object, *, default: str = "") -> str:
    normalized = str(value or "").strip()
    return normalized or default


def approval_audit_lifecycle_counts(events: tuple[dict[str, object], ...]) -> dict[str, int]:
    counts = {
        "approval_requested": 0,
        "approval_decided": 0,
        "approval_expired": 0,
        "approval_required": 0,
        "approval_satisfied": 0,
        "override_submitted": 0,
        "override_decided": 0,
        "override_consumed": 0,
        "resume_hint_emitted": 0,
        "resume_ready": 0,
        "governance_veto": 0,
    }
    for event in events:
        event_type = text(event.get("event_type")).lower()
        if event_type == "approval_requested":
            counts["approval_requested"] += 1
        elif event_type == "approval_decision_recorded":
            counts["approval_decided"] += 1
        elif event_type == "approval_expired":
            counts["approval_expired"] += 1
        elif event_type in {"execution_approval_gate_approval_submitted", "governance_execution_approval_required"}:
            counts["approval_required"] += 1
        elif event_type in {"execution_approval_gate_allowed", "governance_execution_approval_satisfied"}:
            counts["approval_satisfied"] += 1
        elif event_type == "operator_override_submitted":
            counts["override_submitted"] += 1
        elif event_type == "operator_override_decided":
            counts["override_decided"] += 1
        elif event_type == "governance_execution_operator_override_consumed":
            counts["override_consumed"] += 1
        elif event_type == "governance_execution_resume_hint_emitted":
            counts["resume_hint_emitted"] += 1
        elif event_type == "governance_execution_resume_ready":
            counts["resume_ready"] += 1
        elif event_type == "governance_execution_veto":
            counts["governance_veto"] += 1
    return counts


def read_jsonl_events(path) -> tuple[dict[str, object], ...]:
    if not path.exists():
        return ()
    events: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        events.append(json.loads(line))
    return tuple(events)


def canonical_record(*, event_id: str, event_type: str, tenant_id: str, emitted_at, payload: Mapping[str, object]) -> dict[str, object]:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "tenant_id": tenant_id,
        "emitted_at": emitted_at.astimezone(timezone.utc).isoformat(),
        "payload": to_jsonable(dict(payload)),
    }
