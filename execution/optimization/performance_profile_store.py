from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Mapping

from execution.optimization.noise_guard import NoiseMemory
from config.risk_evaluation_policy import DEFAULT_PERFORMANCE_PROFILE_POLICY


PERFORMANCE_PROFILE_SCHEMA_VERSION = 2


def _safe_dict(value: object) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    return {}


def _safe_float(value: object, *, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _safe_int(value: object, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _text(value: object) -> str:
    return str(value or '').strip()


def _safe_key(value: object, *, fallback: str) -> str:
    token = _text(value)
    if not token:
        return fallback
    return token.replace('\\', '_').replace('/', '_').replace(':', '_').replace(' ', '_')


@dataclass(frozen=True)
class RouteAdaptationState:
    route_key: str
    weight: float = 1.0
    success_rate: float = 0.0
    verification_rate: float = 0.0
    roi_score: float = 0.0
    sample_count: int = 0

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> 'RouteAdaptationState':
        return cls(
            route_key=_text(payload.get('route_key') or 'default') or 'default',
            weight=max(DEFAULT_PERFORMANCE_PROFILE_POLICY.route_state_weight_floor, _safe_float(payload.get('weight'), default=1.0)),
            success_rate=max(0.0, min(1.0, _safe_float(payload.get('success_rate')))),
            verification_rate=max(0.0, min(1.0, _safe_float(payload.get('verification_rate')))),
            roi_score=max(0.0, min(1.0, _safe_float(payload.get('roi_score')))),
            sample_count=max(0, _safe_int(payload.get('sample_count'))),
        )


@dataclass(frozen=True)
class EconomicAdaptationState:
    budget_multiplier: float = 1.0
    spend_tightness: float = 0.5
    min_expected_roi: float = 0.25

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> 'EconomicAdaptationState':
        return cls(
            budget_multiplier=max(DEFAULT_PERFORMANCE_PROFILE_POLICY.budget_multiplier_floor, min(DEFAULT_PERFORMANCE_PROFILE_POLICY.budget_multiplier_ceiling, _safe_float(payload.get('budget_multiplier'), default=1.0))),
            spend_tightness=max(0.0, min(1.0, _safe_float(payload.get('spend_tightness'), default=DEFAULT_PERFORMANCE_PROFILE_POLICY.spend_tightness_default))),
            min_expected_roi=max(0.0, min(5.0, _safe_float(payload.get('min_expected_roi'), default=DEFAULT_PERFORMANCE_PROFILE_POLICY.min_expected_roi_default))),
        )


@dataclass(frozen=True)
class ThresholdAdaptationState:
    verification_threshold: float = 0.60
    escalation_threshold: float = 0.35
    retry_threshold: float = 0.55

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> 'ThresholdAdaptationState':
        return cls(
            verification_threshold=max(0.0, min(1.0, _safe_float(payload.get('verification_threshold'), default=0.60))),
            escalation_threshold=max(0.0, min(1.0, _safe_float(payload.get('escalation_threshold'), default=0.35))),
            retry_threshold=max(0.0, min(1.0, _safe_float(payload.get('retry_threshold'), default=0.55))),
        )


@dataclass(frozen=True)
class AdaptationCounters:
    accepted_observations: int = 0
    rejected_observations: int = 0
    executed: int = 0
    verified: int = 0
    achieved: int = 0

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> 'AdaptationCounters':
        return cls(
            accepted_observations=max(0, _safe_int(payload.get('accepted_observations'))),
            rejected_observations=max(0, _safe_int(payload.get('rejected_observations'))),
            executed=max(0, _safe_int(payload.get('executed'))),
            verified=max(0, _safe_int(payload.get('verified'))),
            achieved=max(0, _safe_int(payload.get('achieved'))),
        )


@dataclass(frozen=True)
class PerformanceProfile:
    schema_version: int = PERFORMANCE_PROFILE_SCHEMA_VERSION
    tenant_id: str = ''
    business_id: str = ''
    capability_key: str = ''
    counters: AdaptationCounters = field(default_factory=AdaptationCounters)
    route_states: tuple[RouteAdaptationState, ...] = ()
    economic: EconomicAdaptationState = field(default_factory=EconomicAdaptationState)
    thresholds: ThresholdAdaptationState = field(default_factory=ThresholdAdaptationState)
    score_history: tuple[float, ...] = ()
    noise_memory: NoiseMemory = field(default_factory=NoiseMemory)
    last_noise_reason: str = ''
    last_updated_at: str = ''

    def to_dict(self) -> dict[str, Any]:
        return {
            'schema_version': self.schema_version,
            'tenant_id': self.tenant_id,
            'business_id': self.business_id,
            'capability_key': self.capability_key,
            'counters': asdict(self.counters),
            'route_states': [asdict(x) for x in self.route_states],
            'economic': asdict(self.economic),
            'thresholds': asdict(self.thresholds),
            'score_history': list(self.score_history),
            'noise_memory': self.noise_memory.to_dict(),
            'last_noise_reason': self.last_noise_reason,
            'last_updated_at': self.last_updated_at,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> 'PerformanceProfile':
        return cls(
            schema_version=max(1, _safe_int(payload.get('schema_version'), default=PERFORMANCE_PROFILE_SCHEMA_VERSION)),
            tenant_id=_text(payload.get('tenant_id')),
            business_id=_text(payload.get('business_id')),
            capability_key=_text(payload.get('capability_key')),
            counters=AdaptationCounters.from_dict(_safe_dict(payload.get('counters'))),
            route_states=tuple(RouteAdaptationState.from_dict(x) for x in (payload.get('route_states') or []) if isinstance(x, Mapping)),
            economic=EconomicAdaptationState.from_dict(_safe_dict(payload.get('economic'))),
            thresholds=ThresholdAdaptationState.from_dict(_safe_dict(payload.get('thresholds'))),
            score_history=tuple(max(0.0, min(1.0, _safe_float(v))) for v in (payload.get('score_history') or []))[-100:],
            noise_memory=NoiseMemory.from_dict(_safe_dict(payload.get('noise_memory'))),
            last_noise_reason=_text(payload.get('last_noise_reason')),
            last_updated_at=_text(payload.get('last_updated_at')),
        )


class FilePerformanceProfileStore:
    def __init__(self, *, root_dir: Path, lock_timeout_seconds: float = 5.0) -> None:
        self._root_dir = Path(root_dir)
        self._root_dir.mkdir(parents=True, exist_ok=True)
        self._lock_timeout_seconds = max(0.1, float(lock_timeout_seconds))

    def _path(self, *, tenant_id: str, business_id: str, capability_key: str) -> Path:
        return self._root_dir / _safe_key(tenant_id, fallback='default') / _safe_key(business_id, fallback='business') / f"{_safe_key(capability_key, fallback='unknown')}.json"

    @contextmanager
    def _lock(self, target: Path):
        lock_path = target.with_suffix(target.suffix + '.lock')
        started = time.monotonic()
        while True:
            try:
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                break
            except FileExistsError:
                if time.monotonic() - started >= self._lock_timeout_seconds:
                    raise TimeoutError(f'Timed out waiting for profile lock: {lock_path}')
                time.sleep(0.05)
        try:
            yield
        finally:
            if lock_path.exists():
                lock_path.unlink()

    def load(self, *, tenant_id: str, business_id: str, capability_key: str) -> PerformanceProfile:
        path = self._path(tenant_id=tenant_id, business_id=business_id, capability_key=capability_key)
        if not path.exists():
            return PerformanceProfile(tenant_id=str(tenant_id), business_id=str(business_id), capability_key=str(capability_key))
        try:
            payload = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return PerformanceProfile(tenant_id=str(tenant_id), business_id=str(business_id), capability_key=str(capability_key))
        return PerformanceProfile.from_dict(payload)

    def save(self, profile: PerformanceProfile) -> Path:
        path = self._path(tenant_id=profile.tenant_id, business_id=profile.business_id, capability_key=profile.capability_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock(path):
            payload = json.dumps(profile.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
            fd, temp_name = tempfile.mkstemp(prefix='.adaptive_profile_', suffix='.json', dir=str(path.parent))
            try:
                with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                    handle.write(payload)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_name, path)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
        return path


__all__ = ['AdaptationCounters', 'EconomicAdaptationState', 'FilePerformanceProfileStore', 'PERFORMANCE_PROFILE_SCHEMA_VERSION', 'PerformanceProfile', 'RouteAdaptationState', 'ThresholdAdaptationState']
