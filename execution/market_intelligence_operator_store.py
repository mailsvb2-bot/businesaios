from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import os
from threading import RLock
from typing import Any, Mapping

from governance.persistence_codec import atomic_write_json, read_json_or_default


CANON_MARKET_INTELLIGENCE_OPERATOR_STORE = True


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _text(value: object, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _store_path() -> Path:
    explicit = _text(os.getenv("BUSINESAIOS_MARKET_INTELLIGENCE_OPERATOR_STORE_PATH"))
    if explicit:
        return Path(explicit)
    data_dir = _text(os.getenv("DATA_DIR"), default=".runtime_data")
    return Path(data_dir) / "governance" / "market_intelligence_operator_store.json"


@dataclass(frozen=True)
class ReviewQueueRecord:
    review_id: str
    tenant_id: str
    provider: str
    source_family: str
    external_id: str
    reason: str
    payload: Mapping[str, Any]
    status: str = "open"
    created_at: str = ""
    resolved_at: str | None = None
    resolution: str | None = None
    operator_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "review_id", _text(self.review_id))
        object.__setattr__(self, "tenant_id", _text(self.tenant_id, default="default"))
        object.__setattr__(self, "provider", _text(self.provider))
        object.__setattr__(self, "source_family", _text(self.source_family))
        object.__setattr__(self, "external_id", _text(self.external_id, default="unknown"))
        object.__setattr__(self, "reason", _text(self.reason))
        object.__setattr__(self, "payload", dict(self.payload or {}))
        object.__setattr__(self, "status", _text(self.status, default="open"))
        object.__setattr__(self, "created_at", _text(self.created_at, default=_utc_now()))
        object.__setattr__(self, "resolved_at", _text(self.resolved_at) or None)
        object.__setattr__(self, "resolution", _text(self.resolution) or None)
        object.__setattr__(self, "operator_id", _text(self.operator_id) or None)

    def as_dict(self) -> dict[str, Any]:
        return {
            "review_id": self.review_id,
            "tenant_id": self.tenant_id,
            "provider": self.provider,
            "source_family": self.source_family,
            "external_id": self.external_id,
            "reason": self.reason,
            "payload": dict(self.payload),
            "status": self.status,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
            "resolution": self.resolution,
            "operator_id": self.operator_id,
        }


class PersistentMarketIntelligenceOperatorStore:
    """Persistence surface only. No decision logic here."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path) if path is not None else _store_path()
        self._lock = RLock()
        self._state: dict[str, Any] = {
            "reviews": {},
            "audit_log": [],
            "banlist": [],
            "allowlist": [],
            "next_review_seq": 1,
        }
        self._load()

    def allocate_review_id(self) -> str:
        with self._lock:
            next_seq = int(self._state.get("next_review_seq", 1))
            self._state["next_review_seq"] = next_seq + 1
            self._flush()
            return f"review:{next_seq}"

    def put_review(self, record: ReviewQueueRecord) -> ReviewQueueRecord:
        with self._lock:
            self._state.setdefault("reviews", {})[record.review_id] = record.as_dict()
            self._flush()
            return record

    def get_review(self, review_id: str) -> ReviewQueueRecord | None:
        raw = dict(self._state.get("reviews", {})).get(_text(review_id))
        if not isinstance(raw, dict):
            return None
        return ReviewQueueRecord(**raw)

    def list_reviews(self, *, tenant_id: str | None = None, open_only: bool = False) -> tuple[ReviewQueueRecord, ...]:
        items: list[ReviewQueueRecord] = []
        for raw in dict(self._state.get("reviews", {})).values():
            if not isinstance(raw, dict):
                continue
            item = ReviewQueueRecord(**raw)
            if tenant_id and item.tenant_id != _text(tenant_id):
                continue
            if open_only and item.status != "open":
                continue
            items.append(item)
        items.sort(key=lambda item: (item.created_at, item.review_id))
        return tuple(items)

    def transition_review(self, *, review_id: str, status: str, operator_id: str | None = None, resolution: str | None = None) -> ReviewQueueRecord | None:
        current = self.get_review(review_id)
        if current is None:
            return None
        normalized_status = _text(status, default="open")
        updated = ReviewQueueRecord(
            review_id=current.review_id,
            tenant_id=current.tenant_id,
            provider=current.provider,
            source_family=current.source_family,
            external_id=current.external_id,
            reason=current.reason,
            payload=current.payload,
            status=normalized_status,
            created_at=current.created_at,
            resolved_at=_utc_now() if normalized_status == "resolved" else None,
            resolution=_text(resolution) or None,
            operator_id=_text(operator_id) or None,
        )
        return self.put_review(updated)

    def resolve_review(self, *, review_id: str, resolution: str, operator_id: str) -> ReviewQueueRecord | None:
        return self.transition_review(review_id=review_id, status="resolved", operator_id=operator_id, resolution=resolution)

    def add_audit(self, *, action: str, payload: Mapping[str, Any]) -> None:
        with self._lock:
            self._state.setdefault("audit_log", []).append({"at": _utc_now(), "action": _text(action), "payload": dict(payload or {})})
            audit = list(self._state.get("audit_log", []))
            if len(audit) > 2000:
                self._state["audit_log"] = audit[-2000:]
            self._flush()

    def audit_log(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(item) for item in list(self._state.get("audit_log", [])) if isinstance(item, dict))

    def add_ban(self, *, tenant_id: str, provider: str, scope_key: str) -> None:
        with self._lock:
            entry = [ _text(tenant_id, default="default"), _text(provider), _text(scope_key) ]
            if entry not in self._state.setdefault("banlist", []):
                self._state["banlist"].append(entry)
                self._flush()

    def add_allow(self, *, tenant_id: str, provider: str, scope_key: str) -> None:
        with self._lock:
            entry = [ _text(tenant_id, default="default"), _text(provider), _text(scope_key) ]
            if entry not in self._state.setdefault("allowlist", []):
                self._state["allowlist"].append(entry)
                self._flush()

    def is_banned(self, *, tenant_id: str, provider: str, scope_key: str) -> bool:
        key = [_text(tenant_id, default="default"), _text(provider), _text(scope_key)]
        return key in list(self._state.get("banlist", [])) and key not in list(self._state.get("allowlist", []))

    def snapshot(self) -> dict[str, Any]:
        return {
            "review_queue": [item.as_dict() for item in self.list_reviews()],
            "audit_log": list(self.audit_log()),
            "banlist": [tuple(item) for item in list(self._state.get("banlist", []))],
            "allowlist": [tuple(item) for item in list(self._state.get("allowlist", []))],
        }

    def _load(self) -> None:
        raw = read_json_or_default(self._path, default=self._state)
        if isinstance(raw, dict):
            self._state = {
                "reviews": dict(raw.get("reviews", {})),
                "audit_log": list(raw.get("audit_log", [])),
                "banlist": list(raw.get("banlist", [])),
                "allowlist": list(raw.get("allowlist", [])),
                "next_review_seq": int(raw.get("next_review_seq", 1)),
            }

    def _flush(self) -> None:
        atomic_write_json(self._path, self._state)


__all__ = [
    "CANON_MARKET_INTELLIGENCE_OPERATOR_STORE",
    "PersistentMarketIntelligenceOperatorStore",
    "ReviewQueueRecord",
]
