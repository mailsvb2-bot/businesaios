from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from governance.persistence_codec import ensure_parent_dir, to_jsonable


CANON_DECISION_AUDIT_JSONL_STORE = True


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class DecisionAuditEvent:
    tenant_id: str
    decision_id: str
    action: str
    payload: Mapping[str, Any]
    trace: Mapping[str, Any] | None = None
    emitted_at: datetime = field(default_factory=utc_now)
    actor_id: str | None = None
    correlation_id: str | None = None

    def validate(self) -> None:
        if not str(self.tenant_id or "").strip():
            raise ValueError("tenant_id is required")
        if not str(self.decision_id or "").strip():
            raise ValueError("decision_id is required")
        if not str(self.action or "").strip():
            raise ValueError("action is required")
        if self.emitted_at.tzinfo is None:
            raise ValueError("emitted_at must be timezone-aware")


class JsonlDecisionAuditStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        ensure_parent_dir(self._path)
        if not self._path.exists():
            self._path.touch()

    @property
    def path(self) -> Path:
        return self._path

    def append(self, ev: DecisionAuditEvent) -> None:
        ev.validate()
        rec = {str(k): to_jsonable(v) for k, v in asdict(ev).items()}
        rec["previous_hash"] = self._last_hash()
        rec["record_hash"] = self._record_hash({k: v for k, v in rec.items()})
        with self._path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True))
            f.write("\n")

    def list_by_tenant(self, *, tenant_id: str, limit: int = 500) -> tuple[dict[str, Any], ...]:
        items = [row for row in reversed(self._read_all()) if row.get("tenant_id") == str(tenant_id)]
        return tuple(items[: max(0, int(limit))])

    def validate_chain(self) -> None:
        previous_hash = "GENESIS"
        for row in self._read_all():
            if row.get("previous_hash") != previous_hash:
                raise ValueError("decision audit previous_hash mismatch")
            expected_hash = self._record_hash({k: v for k, v in row.items() if k != "record_hash"})
            if row.get("record_hash") != expected_hash:
                raise ValueError("decision audit record_hash mismatch")
            previous_hash = expected_hash

    def _last_hash(self) -> str:
        rows = self._read_all()
        if not rows:
            return "GENESIS"
        return str(rows[-1].get("record_hash") or "GENESIS")

    def _read_all(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return rows

    @staticmethod
    def _record_hash(payload: dict[str, Any]) -> str:
        return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
