from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from runtime.bootstrap.bootstrap_contract import (
    BootstrapAuditEvent,
    BootstrapEnvironment,
    BootstrapStatus,
)


def _audit_path(env: BootstrapEnvironment) -> Path:
    return env.runtime_dir / "bootstrap" / "audit_trail.jsonl"

def build_bootstrap_audit_event(
    *,
    status: BootstrapStatus,
    code: str,
    message: str,
    details: Mapping[str, str] | None = None,
) -> BootstrapAuditEvent:
    return BootstrapAuditEvent(
        timestamp=datetime.now(UTC),
        status=status,
        code=code,
        message=message,
        details=dict(details or {}),
    )

def append_bootstrap_audit_event(
    *,
    env: BootstrapEnvironment,
    event: BootstrapAuditEvent,
) -> Path | None:
    path = _audit_path(env)
    payload = asdict(event)
    payload["timestamp"] = event.timestamp.isoformat()
    payload["status"] = event.status.value
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    except OSError:
        return None
    return path
