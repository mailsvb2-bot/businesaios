from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Mapping

CANON_CONNECTOR_CIRCUIT_BREAKER = True


def _connector_control_plane_dir() -> Path:
    data_dir = os.getenv('BUSINESAIOS_DATA_DIR', os.getenv('DATA_DIR', 'data')).strip() or 'data'
    root = Path(data_dir) / 'connectors'
    root.mkdir(parents=True, exist_ok=True)
    return root


def connector_circuit_breaker_path() -> Path:
    return _connector_control_plane_dir() / 'connector_circuit_breaker_state.json'


def _atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix='.connector_breaker_', suffix='.json', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
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


class BreakerState(str, Enum):
    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half_open'


@dataclass(frozen=True)
class CircuitBreakerRule:
    connector_id: str
    operation: str = '*'
    provider: str = '*'
    version: str = '*'
    failure_threshold: int = 3
    recovery_timeout_seconds: float = 60.0
    half_open_max_calls: int = 1
    success_threshold: int = 1
    half_open_window_seconds: float = 30.0
    trip_reasons: tuple[str, ...] = (
        'timeout',
        'transport_error',
        'health_probe_exception',
        'consecutive_failures',
        'stale_health_sample',
        'exception',
        'retry_exhausted',
        'result_error',
        'connector_unavailable',
        'temporarily_unavailable',
        'upstream_5xx',
        'rate_limited',
        'throttled',
        'blocked',
    )

    def __post_init__(self) -> None:
        connector_id = str(self.connector_id or '').strip()
        if not connector_id:
            raise ValueError('connector_id is required')
        if int(self.failure_threshold) <= 0:
            raise ValueError('failure_threshold must be > 0')
        if float(self.recovery_timeout_seconds) <= 0:
            raise ValueError('recovery_timeout_seconds must be > 0')
        if int(self.half_open_max_calls) <= 0:
            raise ValueError('half_open_max_calls must be > 0')
        if int(self.success_threshold) <= 0:
            raise ValueError('success_threshold must be > 0')
        if float(self.half_open_window_seconds) <= 0:
            raise ValueError('half_open_window_seconds must be > 0')
        object.__setattr__(self, 'connector_id', connector_id)
        object.__setattr__(self, 'operation', str(self.operation or '*').strip() or '*')
        object.__setattr__(self, 'provider', str(self.provider or '*').strip() or '*')
        object.__setattr__(self, 'version', str(self.version or '*').strip() or '*')
        object.__setattr__(
            self,
            'trip_reasons',
            tuple(sorted({str(item).strip() for item in self.trip_reasons if str(item).strip()})),
        )

    def matches(self, *, connector_id: str, provider: str, version: str, operation: str) -> bool:
        if self.connector_id != '*' and self.connector_id != str(connector_id).strip():
            return False
        if self.provider != '*' and self.provider != str(provider).strip():
            return False
        if self.version != '*' and self.version != str(version).strip():
            return False
        if self.operation != '*' and self.operation != str(operation).strip():
            return False
        return True

    def trips_on(self, reason: str) -> bool:
        return str(reason or '').strip() in set(self.trip_reasons)


@dataclass(frozen=True)
class BreakerPermit:
    allowed: bool
    state: str
    reason: str
    connector_id: str
    provider: str
    version: str
    operation: str
    blocked_until: float | None = None


@dataclass(frozen=True)
class CircuitBreakerSnapshot:
    connector_id: str
    provider: str
    version: str
    operation: str
    state: str
    failure_count: int
    success_count: int
    opened_at: float | None
    blocked_until: float | None
    last_failure_reason: str | None
    last_failure_at: float | None
    last_success_at: float | None
    half_open_in_flight: int
    open_count: int
    half_open_first_probe_at: float | None
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass
class _BreakerRecord:
    state: str = BreakerState.CLOSED.value
    failure_count: int = 0
    success_count: int = 0
    opened_at: float | None = None
    blocked_until: float | None = None
    last_failure_reason: str | None = None
    last_failure_at: float | None = None
    last_success_at: float | None = None
    half_open_in_flight: int = 0
    open_count: int = 0
    half_open_first_probe_at: float | None = None
    metadata: dict[str, object] = field(default_factory=dict)


class ConnectorCircuitBreaker:
    def __init__(
        self,
        *,
        default_rule: CircuitBreakerRule | None = None,
        rules: tuple[CircuitBreakerRule, ...] = (),
        state_path: str | Path | None = None,
        time_fn: Callable[[], float] | None = None,
    ) -> None:
        self._default_rule = default_rule or CircuitBreakerRule(connector_id='*')
        self._rules = list(rules)
        self._state_path = Path(state_path) if state_path is not None else connector_circuit_breaker_path()
        self._time = time_fn or time.time
        self._state: dict[tuple[str, str, str, str], _BreakerRecord] = {}
        self._lock = threading.RLock()
        self._load_state()

    def register_rule(self, rule: CircuitBreakerRule) -> None:
        with self._lock:
            self._rules.append(rule)

    def rule_for(self, *, connector_id: str, provider: str, version: str, operation: str) -> CircuitBreakerRule:
        matches = [
            rule
            for rule in self._rules
            if rule.matches(connector_id=connector_id, provider=provider, version=version, operation=operation)
        ]
        if matches:
            matches.sort(
                key=lambda item: (
                    0 if item.connector_id != '*' else 1,
                    0 if item.provider != '*' else 1,
                    0 if item.version != '*' else 1,
                    0 if item.operation != '*' else 1,
                )
            )
            return matches[0]
        if self._default_rule.matches(connector_id=connector_id, provider=provider, version=version, operation=operation):
            return self._default_rule
        return CircuitBreakerRule(connector_id=str(connector_id).strip())

    def allow_call(self, *, connector_id: str, provider: str, version: str, operation: str) -> BreakerPermit:
        key = self._key(connector_id=connector_id, provider=provider, version=version, operation=operation)
        with self._lock:
            rule = self.rule_for(connector_id=connector_id, provider=provider, version=version, operation=operation)
            record = self._state.setdefault(key, _BreakerRecord())
            now = float(self._time())
            if record.state == BreakerState.OPEN.value:
                blocked_until = float(record.blocked_until or 0.0)
                if blocked_until > now:
                    return BreakerPermit(False, record.state, 'circuit_open', connector_id, provider, version, operation, record.blocked_until)
                record.state = BreakerState.HALF_OPEN.value
                record.half_open_in_flight = 0
                record.success_count = 0
                record.half_open_first_probe_at = None
                self._flush_state_locked()
            if record.state == BreakerState.HALF_OPEN.value:
                window_started = float(record.half_open_first_probe_at or now)
                if record.half_open_first_probe_at is None:
                    record.half_open_first_probe_at = now
                elif (now - window_started) > float(rule.half_open_window_seconds):
                    record.half_open_first_probe_at = now
                    record.half_open_in_flight = 0
                    record.success_count = 0
                if int(record.half_open_in_flight) >= int(rule.half_open_max_calls):
                    return BreakerPermit(False, record.state, 'half_open_budget_exhausted', connector_id, provider, version, operation, record.blocked_until)
                record.half_open_in_flight += 1
                self._flush_state_locked()
                return BreakerPermit(True, record.state, 'half_open_probe', connector_id, provider, version, operation, record.blocked_until)
            return BreakerPermit(True, record.state, 'closed', connector_id, provider, version, operation, record.blocked_until)

    def record_success(self, *, connector_id: str, provider: str, version: str, operation: str, metadata: Mapping[str, object] | None = None) -> CircuitBreakerSnapshot:
        key = self._key(connector_id=connector_id, provider=provider, version=version, operation=operation)
        with self._lock:
            rule = self.rule_for(connector_id=connector_id, provider=provider, version=version, operation=operation)
            record = self._state.setdefault(key, _BreakerRecord())
            record.last_success_at = float(self._time())
            record.metadata = dict(metadata or {})
            if record.state == BreakerState.HALF_OPEN.value:
                record.success_count += 1
                record.half_open_in_flight = max(0, int(record.half_open_in_flight) - 1)
                if int(record.success_count) >= int(rule.success_threshold):
                    self._close_locked(record)
            else:
                self._close_locked(record)
            self._flush_state_locked()
            return self._snapshot_locked(connector_id=connector_id, provider=provider, version=version, operation=operation)

    def record_failure(self, *, connector_id: str, provider: str, version: str, operation: str, reason: str, metadata: Mapping[str, object] | None = None) -> CircuitBreakerSnapshot:
        key = self._key(connector_id=connector_id, provider=provider, version=version, operation=operation)
        with self._lock:
            rule = self.rule_for(connector_id=connector_id, provider=provider, version=version, operation=operation)
            record = self._state.setdefault(key, _BreakerRecord())
            now = float(self._time())
            normalized_reason = str(reason or '').strip() or 'failure'
            record.last_failure_reason = normalized_reason
            record.last_failure_at = now
            record.metadata = dict(metadata or {})
            if record.state == BreakerState.HALF_OPEN.value:
                record.half_open_in_flight = max(0, int(record.half_open_in_flight) - 1)
                self._open_locked(record, rule=rule, now=now)
            else:
                record.failure_count += 1
                if rule.trips_on(normalized_reason) and int(record.failure_count) >= int(rule.failure_threshold):
                    self._open_locked(record, rule=rule, now=now)
            self._flush_state_locked()
            return self._snapshot_locked(connector_id=connector_id, provider=provider, version=version, operation=operation)

    def force_open(self, *, connector_id: str, provider: str, version: str, operation: str, reason: str = 'forced_open') -> None:
        key = self._key(connector_id=connector_id, provider=provider, version=version, operation=operation)
        with self._lock:
            rule = self.rule_for(connector_id=connector_id, provider=provider, version=version, operation=operation)
            record = self._state.setdefault(key, _BreakerRecord())
            now = float(self._time())
            record.last_failure_reason = str(reason or 'forced_open')
            record.last_failure_at = now
            self._open_locked(record, rule=rule, now=now)
            self._flush_state_locked()

    def force_close(self, *, connector_id: str, provider: str, version: str, operation: str) -> None:
        key = self._key(connector_id=connector_id, provider=provider, version=version, operation=operation)
        with self._lock:
            record = self._state.setdefault(key, _BreakerRecord())
            self._close_locked(record)
            self._flush_state_locked()

    def snapshot_for(self, *, connector_id: str, provider: str, version: str, operation: str) -> CircuitBreakerSnapshot:
        with self._lock:
            return self._snapshot_locked(connector_id=connector_id, provider=provider, version=version, operation=operation)

    def snapshot(self) -> tuple[dict[str, object], ...]:
        with self._lock:
            return tuple(
                {
                    'connector_id': row.connector_id,
                    'provider': row.provider,
                    'version': row.version,
                    'operation': row.operation,
                    'state': row.state,
                    'failure_count': row.failure_count,
                    'success_count': row.success_count,
                    'opened_at': row.opened_at,
                    'blocked_until': row.blocked_until,
                    'last_failure_reason': row.last_failure_reason,
                    'last_failure_at': row.last_failure_at,
                    'last_success_at': row.last_success_at,
                    'half_open_in_flight': row.half_open_in_flight,
                    'open_count': row.open_count,
                    'metadata': dict(row.metadata),
                }
                for row in [self._snapshot_locked(connector_id=k[0], provider=k[1], version=k[2], operation=k[3]) for k in sorted(self._state)]
            )

    def _snapshot_locked(self, *, connector_id: str, provider: str, version: str, operation: str) -> CircuitBreakerSnapshot:
        record = self._state.setdefault(self._key(connector_id=connector_id, provider=provider, version=version, operation=operation), _BreakerRecord())
        return CircuitBreakerSnapshot(
            connector_id=connector_id,
            provider=provider,
            version=version,
            operation=operation,
            state=str(record.state),
            failure_count=int(record.failure_count),
            success_count=int(record.success_count),
            opened_at=record.opened_at,
            blocked_until=record.blocked_until,
            last_failure_reason=record.last_failure_reason,
            last_failure_at=record.last_failure_at,
            last_success_at=record.last_success_at,
            half_open_in_flight=int(record.half_open_in_flight),
            open_count=int(record.open_count),
            half_open_first_probe_at=record.half_open_first_probe_at,
            metadata=dict(record.metadata),
        )

    def _open_locked(self, record: _BreakerRecord, *, rule: CircuitBreakerRule, now: float) -> None:
        record.state = BreakerState.OPEN.value
        record.blocked_until = now + float(rule.recovery_timeout_seconds)
        record.opened_at = now
        record.success_count = 0
        record.half_open_in_flight = 0
        record.open_count += 1
        record.half_open_first_probe_at = None

    def _close_locked(self, record: _BreakerRecord) -> None:
        record.state = BreakerState.CLOSED.value
        record.failure_count = 0
        record.success_count = 0
        record.opened_at = None
        record.blocked_until = None
        record.half_open_in_flight = 0

    def _key(self, *, connector_id: str, provider: str, version: str, operation: str) -> tuple[str, str, str, str]:
        return (str(connector_id).strip(), str(provider).strip(), str(version).strip(), str(operation).strip())

    def _load_state(self) -> None:
        if not self._state_path.exists():
            return
        try:
            payload = json.loads(self._state_path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return
        restored: dict[tuple[str, str, str, str], _BreakerRecord] = {}
        for row in payload.get('state') or ():
            if not isinstance(row, dict):
                continue
            key = (
                str(row.get('connector_id') or '').strip(),
                str(row.get('provider') or '').strip(),
                str(row.get('version') or '').strip(),
                str(row.get('operation') or '').strip(),
            )
            if not all(key):
                continue
            restored[key] = _BreakerRecord(
                state=str(row.get('state') or BreakerState.CLOSED.value),
                failure_count=int(row.get('failure_count') or 0),
                success_count=int(row.get('success_count') or 0),
                opened_at=None if row.get('opened_at') is None else float(row.get('opened_at')),
                blocked_until=None if row.get('blocked_until') is None else float(row.get('blocked_until')),
                last_failure_reason=None if row.get('last_failure_reason') is None else str(row.get('last_failure_reason')),
                last_failure_at=None if row.get('last_failure_at') is None else float(row.get('last_failure_at')),
                last_success_at=None if row.get('last_success_at') is None else float(row.get('last_success_at')),
                half_open_in_flight=int(row.get('half_open_in_flight') or 0),
                open_count=int(row.get('open_count') or 0),
                metadata=dict(row.get('metadata') or {}),
            )
        self._state = restored

    def _flush_state_locked(self) -> None:
        if self._state_path is None:
            return
        rows = [
            {
                'connector_id': k[0],
                'provider': k[1],
                'version': k[2],
                'operation': k[3],
                'state': v.state,
                'failure_count': v.failure_count,
                'success_count': v.success_count,
                'opened_at': v.opened_at,
                'blocked_until': v.blocked_until,
                'last_failure_reason': v.last_failure_reason,
                'last_failure_at': v.last_failure_at,
                'last_success_at': v.last_success_at,
                'half_open_in_flight': v.half_open_in_flight,
                'open_count': v.open_count,
                'metadata': dict(v.metadata),
            }
            for k, v in sorted(self._state.items())
        ]
        _atomic_write_json(self._state_path, {'state': rows})


__all__ = [
    'BreakerPermit',
    'BreakerState',
    'CANON_CONNECTOR_CIRCUIT_BREAKER',
    'CircuitBreakerRule',
    'CircuitBreakerSnapshot',
    'ConnectorCircuitBreaker',
    'connector_circuit_breaker_path',
]
