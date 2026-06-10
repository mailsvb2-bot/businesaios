from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping

from connectors.platform.connector_registry import ConnectorRegistry
from interfaces.common.connector_health import ConnectorHealth

CANON_CONNECTOR_HEALTH_MONITOR = True


def _connector_control_plane_dir() -> Path:
    data_dir = os.getenv("BUSINESAIOS_DATA_DIR", os.getenv("DATA_DIR", "data")).strip() or "data"
    root = Path(data_dir) / "connectors"
    root.mkdir(parents=True, exist_ok=True)
    return root


def connector_health_monitor_path() -> Path:
    return _connector_control_plane_dir() / "connector_health_history.json"


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=".connector_health_", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
        try:
            dir_fd = os.open(str(path.parent), os.O_DIRECTORY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except Exception:
            pass
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _sample_to_payload(sample: "ConnectorHealthSample") -> dict[str, object]:
    return {
        "connector_id": sample.connector_id,
        "provider": sample.provider,
        "version": sample.version,
        "healthy": sample.healthy,
        "reason": sample.reason,
        "recorded_at": sample.recorded_at.isoformat(),
        "metadata": dict(sample.metadata or {}),
    }


def _sample_from_payload(payload: dict[str, object]) -> "ConnectorHealthSample":
    return ConnectorHealthSample(
        connector_id=str(payload.get("connector_id") or "").strip(),
        provider=str(payload.get("provider") or "").strip(),
        version=str(payload.get("version") or "").strip(),
        healthy=bool(payload.get("healthy")),
        reason=str(payload.get("reason") or "").strip(),
        recorded_at=_normalize_loaded_datetime(payload.get("recorded_at")),
        metadata=dict(payload.get("metadata") or {}),
    )




def _normalize_loaded_datetime(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ConnectorHealthSample:
    connector_id: str
    provider: str
    version: str
    healthy: bool
    reason: str
    recorded_at: datetime = field(default_factory=utc_now)
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if not str(self.connector_id or '').strip():
            raise ValueError('connector_id is required')
        if not str(self.provider or '').strip():
            raise ValueError('provider is required')
        if not str(self.version or '').strip():
            raise ValueError('version is required')
        if self.recorded_at.tzinfo is None:
            raise ValueError('recorded_at must be timezone-aware')


@dataclass(frozen=True)
class ConnectorHealthVerdict:
    connector_id: str
    provider: str
    version: str
    healthy: bool
    reason: str
    consecutive_failures: int
    last_probe_at: str | None
    stale: bool
    latency_ms: float | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)


class ConnectorHealthMonitor:
    def __init__(
        self,
        *,
        registry: ConnectorRegistry,
        max_history: int = 20,
        consecutive_failure_threshold: int = 2,
        stale_after_seconds: int = 300,
        history_path: str | Path | None = None,
    ) -> None:
        if int(max_history) <= 0:
            raise ValueError('max_history must be > 0')
        if int(consecutive_failure_threshold) <= 0:
            raise ValueError('consecutive_failure_threshold must be > 0')
        if int(stale_after_seconds) <= 0:
            raise ValueError('stale_after_seconds must be > 0')
        self._registry = registry
        self._max_history = int(max_history)
        self._consecutive_failure_threshold = int(consecutive_failure_threshold)
        self._stale_after = timedelta(seconds=int(stale_after_seconds))
        self._history: dict[tuple[str, str, str], list[ConnectorHealthSample]] = {}
        self._history_path = None if history_path is None else Path(history_path)
        if history_path is None:
            backend = os.getenv('BUSINESAIOS_CONNECTOR_HEALTH_BACKEND', 'file').strip().lower()
            if backend != 'memory':
                self._history_path = connector_health_monitor_path()
        self._lock = threading.RLock()
        self._load_history()

    def probe(self, *, connector_id: str, version: str | None = None, provider: str | None = None) -> ConnectorHealthSample:
        entry = self._registry.get_entry(connector_id=connector_id, version=version, provider=provider)
        try:
            health: ConnectorHealth = entry.connector.health()
            sample = ConnectorHealthSample(
                connector_id=str(entry.connector_id),
                provider=str(entry.provider),
                version=str(entry.version),
                healthy=bool(health.healthy),
                reason=str(health.reason or ''),
                metadata=dict(health.metadata or {}),
            )
        except Exception as exc:
            sample = ConnectorHealthSample(
                connector_id=str(entry.connector_id),
                provider=str(entry.provider),
                version=str(entry.version),
                healthy=False,
                reason='health_probe_exception',
                metadata={'error': str(exc), 'exception_type': exc.__class__.__name__},
            )
        self.record(sample)
        return sample

    def record(self, sample: ConnectorHealthSample) -> None:
        sample.validate()
        key = (str(sample.connector_id).strip(), str(sample.provider).strip(), str(sample.version).strip())
        with self._lock:
            history = self._history.setdefault(key, [])
            history.append(sample)
            if len(history) > self._max_history:
                del history[:-self._max_history]
            self._flush_history()

    def latest(self, *, connector_id: str, version: str | None = None, provider: str | None = None) -> ConnectorHealthSample | None:
        entry = self._registry.get_entry(connector_id=connector_id, version=version, provider=provider)
        with self._lock:
            history = self._history.get((str(entry.connector_id), str(entry.provider), str(entry.version)), ())
            return history[-1] if history else None

    def verdict(self, *, connector_id: str, version: str | None = None, provider: str | None = None, probe_if_missing: bool = True) -> ConnectorHealthVerdict:
        entry = self._registry.get_entry(connector_id=connector_id, version=version, provider=provider)
        latest = self.latest(connector_id=entry.connector_id, version=entry.version, provider=entry.provider)
        if latest is None and probe_if_missing:
            latest = self.probe(connector_id=entry.connector_id, version=entry.version, provider=entry.provider)
        if latest is None:
            return ConnectorHealthVerdict(
                connector_id=str(entry.connector_id),
                provider=str(entry.provider),
                version=str(entry.version),
                healthy=False,
                reason='no_health_sample',
                consecutive_failures=0,
                last_probe_at=None,
                stale=True,
                latency_ms=None,
                metadata={},
            )
        failures = 0
        with self._lock:
            history = list(self._history.get((str(entry.connector_id), str(entry.provider), str(entry.version)), ()))
        for item in reversed(history):
            if item.healthy:
                break
            failures += 1
        stale = (utc_now() - latest.recorded_at) > self._stale_after
        healthy = bool(latest.healthy) and failures < self._consecutive_failure_threshold and not stale
        reason = str(latest.reason or '')
        if stale:
            reason = 'stale_health_sample'
        elif failures >= self._consecutive_failure_threshold:
            reason = 'consecutive_failures'
        latency_ms = None
        try:
            if isinstance(latest.metadata, Mapping):
                raw_latency = latest.metadata.get('latency_ms')
                latency_ms = None if raw_latency is None else float(raw_latency)
        except Exception:
            latency_ms = None
        return ConnectorHealthVerdict(
            connector_id=str(entry.connector_id),
            provider=str(entry.provider),
            version=str(entry.version),
            healthy=healthy,
            reason=reason,
            consecutive_failures=failures,
            last_probe_at=latest.recorded_at.isoformat(),
            stale=stale,
            latency_ms=latency_ms,
            metadata=dict(latest.metadata or {}),
        )

    def is_healthy(self, *, connector_id: str, version: str | None = None, provider: str | None = None) -> bool:
        return bool(self.verdict(connector_id=connector_id, version=version, provider=provider).healthy)

    def snapshot(self) -> dict[str, tuple[dict[str, object], ...]]:
        with self._lock:
            rows = []
            for (connector_id, provider, version), samples in sorted(self._history.items()):
                rows.append({
                    'connector_id': connector_id,
                    'provider': provider,
                    'version': version,
                    'samples': tuple(_sample_to_payload(sample) for sample in samples[-self._max_history:]),
                })
        return {'history': tuple(rows)}

    def degraded_connectors(self) -> tuple[dict[str, object], ...]:
        rows: list[dict[str, object]] = []
        for entry in self._registry.list_entries(enabled_only=False):
            verdict = self.verdict(
                connector_id=entry.connector_id,
                version=entry.version,
                provider=entry.provider,
                probe_if_missing=False,
            )
            if verdict.healthy:
                continue
            rows.append(
                {
                    'connector_id': str(verdict.connector_id),
                    'provider': str(verdict.provider),
                    'version': str(verdict.version),
                    'healthy': bool(verdict.healthy),
                    'reason': str(verdict.reason),
                    'consecutive_failures': int(verdict.consecutive_failures),
                    'last_probe_at': verdict.last_probe_at,
                    'stale': bool(verdict.stale),
                    'latency_ms': verdict.latency_ms,
                    'metadata': dict(verdict.metadata),
                }
            )
        return tuple(rows)



    def _load_history(self) -> None:
        if self._history_path is None or not self._history_path.exists():
            return
        try:
            payload = json.loads(self._history_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        history = {}
        for row in payload.get("history") or []:
            if not isinstance(row, dict):
                continue
            try:
                sample = _sample_from_payload(row)
            except Exception:
                continue
            key = (sample.connector_id, sample.provider, sample.version)
            history.setdefault(key, []).append(sample)
        with self._lock:
            self._history = history

    def _flush_history(self) -> None:
        if self._history_path is None:
            return
        rows: list[dict[str, object]] = []
        for samples in self._history.values():
            for sample in samples[-self._max_history:]:
                rows.append(_sample_to_payload(sample))
        _atomic_write_json(self._history_path, {"history": rows})


def build_default_connector_health_monitor(*, registry: ConnectorRegistry) -> ConnectorHealthMonitor:
    mode = os.getenv("BUSINESAIOS_CONNECTOR_HEALTH_BACKEND", "file").strip().lower()
    if mode == "memory":
        return ConnectorHealthMonitor(registry=registry, history_path=None)
    return ConnectorHealthMonitor(registry=registry, history_path=connector_health_monitor_path())

__all__ = [
    'CANON_CONNECTOR_HEALTH_MONITOR',
    'ConnectorHealthMonitor',
    'ConnectorHealthSample',
    'ConnectorHealthVerdict',
    'build_default_connector_health_monitor',
    'utc_now',
    'connector_health_monitor_path',
]
