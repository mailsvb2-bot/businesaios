from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


CANON_DEPLOYMENT_MIGRATION_GUARD = True


class MigrationGuardError(RuntimeError):
    """Raised when deployment must not proceed due to migration risk."""


@dataclass(frozen=True)
class MigrationRecord:
    version: int
    name: str

    def __post_init__(self) -> None:
        if int(self.version) < 1:
            raise ValueError("migration version must be >= 1")
        if not str(self.name or "").strip():
            raise ValueError("migration name is required")


@dataclass(frozen=True)
class MigrationAssessment:
    current_version: int
    target_version: int
    pending_versions: tuple[int, ...] = field(default_factory=tuple)
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def blocked(self) -> bool:
        return bool(self.reasons)


@dataclass(frozen=True)
class MigrationGuardPolicy:
    allow_major_jump_without_approval: bool = False
    max_linear_jump: int = 1
    allow_version_regression: bool = False

    def __post_init__(self) -> None:
        if int(self.max_linear_jump) < 0:
            raise ValueError("max_linear_jump must be >= 0")

    def evaluate(
        self,
        *,
        current_version: int,
        target_version: int,
        pending_versions: tuple[int, ...],
    ) -> MigrationAssessment:
        current = int(current_version)
        target = int(target_version)
        pending = tuple(int(item) for item in pending_versions)
        reasons: list[str] = []
        if current < 0:
            reasons.append("current migration version must be >= 0")
        if target < 0:
            reasons.append("target migration version must be >= 0")
        if target < current and not self.allow_version_regression:
            reasons.append("target migration version is lower than current version")
        if pending != tuple(sorted(pending)):
            reasons.append("pending migrations are not sorted ascending")
        if len(set(pending)) != len(pending):
            reasons.append("pending migrations contain duplicates")
        if pending:
            expected = tuple(range(current + 1, target + 1))
            if pending != expected:
                reasons.append("pending migration history is not contiguous")
        elif target > current:
            reasons.append("target version is ahead of current version but pending migrations are empty")
        jump = target - current
        if jump > int(self.max_linear_jump) and not self.allow_major_jump_without_approval:
            reasons.append(
                f"migration jump too large for automatic deploy: current={current} target={target}"
            )
        return MigrationAssessment(
            current_version=current,
            target_version=target,
            pending_versions=pending,
            reasons=tuple(reasons),
        )


def _migration_version(item: object) -> int:
    if isinstance(item, dict):
        return int(item["version"])
    return int(getattr(item, "version"))


class SupportsMigrationVersion(Protocol):
    def current_version(self, executor: object, *, scope: str = ..., component: str = ...) -> int: ...
    def latest_version(self) -> int: ...
    def pending(self, current_version: int) -> tuple[object, ...]: ...


class MigrationGuard:
    def __init__(self, *, policy: MigrationGuardPolicy | None = None) -> None:
        self._policy = policy or MigrationGuardPolicy()

    def assess(
        self,
        *,
        registry: SupportsMigrationVersion,
        executor: object,
        scope: str = "storage",
        component: str = "storage_migrations",
    ) -> MigrationAssessment:
        current_version = int(registry.current_version(executor, scope=scope, component=component))
        target_version = int(registry.latest_version())
        pending_versions = tuple(sorted(_migration_version(item) for item in registry.pending(current_version)))
        return self._policy.evaluate(
            current_version=current_version,
            target_version=target_version,
            pending_versions=pending_versions,
        )

    def assert_safe_to_deploy(
        self,
        *,
        registry: SupportsMigrationVersion,
        executor: object,
        scope: str = "storage",
        component: str = "storage_migrations",
    ) -> MigrationAssessment:
        assessment = self.assess(
            registry=registry,
            executor=executor,
            scope=scope,
            component=component,
        )
        if assessment.blocked:
            joined = "; ".join(assessment.reasons)
            raise MigrationGuardError(f"deployment migration guard blocked release: {joined}")
        return assessment


__all__ = [
    "_migration_version",
    "CANON_DEPLOYMENT_MIGRATION_GUARD",
    "MigrationAssessment",
    "MigrationGuard",
    "MigrationGuardError",
    "MigrationGuardPolicy",
    "MigrationRecord",
]
