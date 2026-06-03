from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import os
from threading import RLock
from typing import Any
from collections.abc import Mapping

from governance.persistence_codec import atomic_write_json, read_json_or_default


CANON_MARKET_INTELLIGENCE_OBSERVABILITY_STORE = True


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _text(value: object, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default


def _store_path() -> Path:
    explicit = _text(os.getenv("BUSINESAIOS_MARKET_INTELLIGENCE_OBSERVABILITY_STORE_PATH"))
    if explicit:
        return Path(explicit)
    data_dir = _text(os.getenv("DATA_DIR"), default=".runtime_data")
    return Path(data_dir) / "observability" / "market_intelligence_observability_store.json"


@dataclass(frozen=True)
class MarketIntelligenceRunSummary:
    run_id: str
    tenant_id: str
    provider: str
    source_family: str
    action_type: str
    status: str
    records_count: int = 0
    quality_score: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _text(self.run_id))
        object.__setattr__(self, "tenant_id", _text(self.tenant_id, default="default"))
        object.__setattr__(self, "provider", _text(self.provider))
        object.__setattr__(self, "source_family", _text(self.source_family))
        object.__setattr__(self, "action_type", _text(self.action_type))
        object.__setattr__(self, "status", _text(self.status, default="unknown"))
        object.__setattr__(self, "records_count", int(self.records_count))
        object.__setattr__(self, "quality_score", float(self.quality_score))
        object.__setattr__(self, "created_at", _text(self.created_at, default=_utc_now()))
        object.__setattr__(self, "metadata", dict(self.metadata or {}))

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "tenant_id": self.tenant_id,
            "provider": self.provider,
            "source_family": self.source_family,
            "action_type": self.action_type,
            "status": self.status,
            "records_count": self.records_count,
            "quality_score": self.quality_score,
            "created_at": self.created_at,
            "metadata": dict(self.metadata or {}),
        }


class PersistentMarketIntelligenceObservabilityStore:
    """Persistence only. No routing, scoring, or decisions."""

    def __init__(self, path: str | Path | None = None, *, max_entries: int = 2000) -> None:
        self._path = Path(path) if path is not None else _store_path()
        self._lock = RLock()
        self._max_entries = max(100, int(max_entries))
        self._state: dict[str, Any] = {
            "runs": [],
            "anomalies": [],
            "provenance_audit": [],
        }
        self._load()

    def append_run(self, summary: MarketIntelligenceRunSummary) -> None:
        with self._lock:
            self._state.setdefault("runs", []).append(summary.as_dict())
            self._trim("runs")
            self._flush()

    def append_anomaly(self, *, tenant_id: str, provider: str, source_family: str, reason: str, payload: Mapping[str, Any] | None = None) -> None:
        with self._lock:
            self._state.setdefault("anomalies", []).append({
                "at": _utc_now(),
                "tenant_id": _text(tenant_id, default="default"),
                "provider": _text(provider),
                "source_family": _text(source_family),
                "reason": _text(reason),
                "payload": dict(payload or {}),
            })
            self._trim("anomalies")
            self._flush()

    def append_provenance(self, *, tenant_id: str, evidence_id: str, provider: str, source_family: str, derived_kind: str, policy_name: str) -> None:
        with self._lock:
            self._state.setdefault("provenance_audit", []).append({
                "at": _utc_now(),
                "tenant_id": _text(tenant_id, default="default"),
                "evidence_id": _text(evidence_id),
                "provider": _text(provider),
                "source_family": _text(source_family),
                "derived_kind": _text(derived_kind),
                "policy_name": _text(policy_name),
            })
            self._trim("provenance_audit")
            self._flush()

    def snapshot(self) -> dict[str, Any]:
        return {
            "runs": list(self._state.get("runs", [])),
            "anomalies": list(self._state.get("anomalies", [])),
            "provenance_audit": list(self._state.get("provenance_audit", [])),
        }

    def _trim(self, key: str) -> None:
        items = list(self._state.get(key, []))
        if len(items) > self._max_entries:
            self._state[key] = items[-self._max_entries :]

    def _load(self) -> None:
        raw = read_json_or_default(self._path, default=self._state)
        if isinstance(raw, dict):
            self._state = {
                "runs": list(raw.get("runs", [])),
                "anomalies": list(raw.get("anomalies", [])),
                "provenance_audit": list(raw.get("provenance_audit", [])),
            }

    def _flush(self) -> None:
        atomic_write_json(self._path, self._state)


__all__ = [
    "CANON_MARKET_INTELLIGENCE_OBSERVABILITY_STORE",
    "MarketIntelligenceRunSummary",
    "PersistentMarketIntelligenceObservabilityStore",
]
