from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Mapping, Protocol


CANON_DEPLOYMENT_HEALTH_CONTRACT = True


class HealthCheckStatus(StrEnum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class HealthSignal(StrEnum):
    LIVENESS = "liveness"
    READINESS = "readiness"
    STARTUP = "startup"
    RELEASE = "release"
    DEPENDENCY = "dependency"
    MIGRATION = "migration"
    OBSERVABILITY = "observ" "ability"
    CONFIGURATION = "configuration"


class HealthExceptionPolicy(StrEnum):
    FAIL_CLOSED = "fail_closed"
    WARN_OPEN = "warn_open"


_STATUS_RANK = {
    HealthCheckStatus.PASS: 0,
    HealthCheckStatus.WARN: 1,
    HealthCheckStatus.FAIL: 2,
}


@dataclass(frozen=True)
class HealthCheckResult:
    name: str
    status: HealthCheckStatus
    signal: HealthSignal
    summary: str
    details: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.name or "").strip():
            raise ValueError("health check name is required")
        if not str(self.summary or "").strip():
            raise ValueError("health check summary is required")

    @property
    def ok(self) -> bool:
        return self.status is not HealthCheckStatus.FAIL

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": self.status.value,
            "signal": self.signal.value,
            "summary": self.summary,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class ReadinessSnapshot:
    service_names: tuple[str, ...] = field(default_factory=tuple)
    component_names: tuple[str, ...] = field(default_factory=tuple)
    runtime_booted: bool = False
    runtime_state_ready: bool = False
    readiness_gate_ready: bool = False
    shutting_down: bool = False
    checked_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    missing_services: tuple[str, ...] = field(default_factory=tuple)
    missing_components: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if len(set(self.service_names)) != len(self.service_names):
            raise ValueError("service_names must be unique")
        if len(set(self.component_names)) != len(self.component_names):
            raise ValueError("component_names must be unique")

    @property
    def service_count(self) -> int:
        return len(self.service_names)

    @property
    def component_count(self) -> int:
        return len(self.component_names)

    @property
    def ready(self) -> bool:
        return (
            self.runtime_booted
            and self.runtime_state_ready
            and self.readiness_gate_ready
            and not self.shutting_down
            and not self.missing_services
            and not self.missing_components
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "service_names": list(self.service_names),
            "component_names": list(self.component_names),
            "service_count": self.service_count,
            "component_count": self.component_count,
            "runtime_booted": self.runtime_booted,
            "runtime_state_ready": self.runtime_state_ready,
            "readiness_gate_ready": self.readiness_gate_ready,
            "shutting_down": self.shutting_down,
            "missing_services": list(self.missing_services),
            "missing_components": list(self.missing_components),
            "checked_at": self.checked_at,
            "ready": self.ready,
        }


@dataclass(frozen=True)
class HealthReport:
    service: str
    overall_status: HealthCheckStatus
    checks: tuple[HealthCheckResult, ...]
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    version: str | None = None
    release_id: str | None = None

    def __post_init__(self) -> None:
        if not str(self.service or "").strip():
            raise ValueError("service is required")
        if not self.checks:
            raise ValueError("health report must contain at least one check")
        names = tuple(item.name for item in self.checks)
        if len(set(names)) != len(names):
            raise ValueError("health report checks must be unique by name")

    @property
    def ok(self) -> bool:
        return self.overall_status is not HealthCheckStatus.FAIL

    @classmethod
    def aggregate(
        cls,
        *,
        service: str,
        checks: tuple[HealthCheckResult, ...],
        version: str | None = None,
        release_id: str | None = None,
    ) -> "HealthReport":
        if not checks:
            raise ValueError("checks must not be empty")
        overall = max((item.status for item in checks), key=_STATUS_RANK.__getitem__)
        return cls(
            service=str(service).strip(),
            overall_status=overall,
            checks=checks,
            version=None if version is None else str(version),
            release_id=None if release_id is None else str(release_id),
        )

    def counts(self) -> dict[str, int]:
        counts = {status.value: 0 for status in HealthCheckStatus}
        for item in self.checks:
            counts[item.status.value] = counts.get(item.status.value, 0) + 1
        return counts

    def to_dict(self) -> dict[str, object]:
        return {
            "service": self.service,
            "overall_status": self.overall_status.value,
            "counts": self.counts(),
            "checks": [item.to_dict() for item in self.checks],
            "generated_at": self.generated_at,
            "version": self.version,
            "release_id": self.release_id,
        }


class HealthCheck(Protocol):
    def __call__(self) -> HealthCheckResult: ...


__all__ = [
    "CANON_DEPLOYMENT_HEALTH_CONTRACT",
    "HealthCheck",
    "HealthCheckResult",
    "HealthCheckStatus",
    "HealthExceptionPolicy",
    "HealthReport",
    "HealthSignal",
    "ReadinessSnapshot",
]
