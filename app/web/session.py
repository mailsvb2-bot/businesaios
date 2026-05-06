from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from security.payload_redaction import PayloadRedactor
from security.session_policy import SessionPolicy


@dataclass
class SessionStore:
    redactor: PayloadRedactor = field(default_factory=PayloadRedactor)
    policy: SessionPolicy = field(default_factory=SessionPolicy)

    def build(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        now = _parse_dt(data.get("now"), fallback=datetime.now(timezone.utc))
        created_at = _parse_dt(data.get("created_at") or data.get("issued_at"))
        last_seen_at = _parse_dt(data.get("last_seen_at") or data.get("expires_at"))
        if created_at is None or last_seen_at is None:
            allowed = False
            invalidate_session = True
            rotate_session = False
            age_seconds = None
            idle_seconds = None
            reason = 'missing_timestamps'
        else:
            verdict = self.policy.evaluate(created_at=created_at, last_seen_at=last_seen_at, now=now)
            allowed = verdict.allowed
            invalidate_session = verdict.invalidate_session
            rotate_session = verdict.rotate_session
            age_seconds = max(0, int((now - created_at).total_seconds()))
            idle_seconds = max(0, int((now - last_seen_at).total_seconds()))
            reason = verdict.reason
        redacted = self.redactor.redact(data)
        redacted["security"] = {
            "session": {
                "allowed": allowed,
                "invalidate_session": invalidate_session,
                "rotate_session": rotate_session,
                "reason": reason,
                "age_seconds": age_seconds,
                "idle_seconds": idle_seconds,
            },
            "tenant": {"bound": bool(str(data.get("tenant_id") or "").strip())},
        }
        return {"kind": "session", "payload": redacted}


def _parse_dt(value: Any, *, fallback: datetime | None = None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return fallback
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


__all__ = ["SessionStore"]
