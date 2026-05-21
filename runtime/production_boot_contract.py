from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping


class ProductionStorageMode(str, Enum):
    SQLITE_DEV = "sqlite_dev"
    POSTGRES_REQUIRED = "postgres_required"


@dataclass(frozen=True)
class ProductionBootInput:
    env: str
    app_profile: str
    run_mode: str
    database_url: str
    postgres_enabled: bool
    migrations_required: bool = True
    release_id: str = "unknown"

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "ProductionBootInput":
        return cls(
            env=str(env.get("ENV") or env.get("APP_ENV") or "").strip().lower(),
            app_profile=str(env.get("APP_PROFILE") or "").strip().lower(),
            run_mode=str(env.get("RUN_MODE") or "").strip().lower(),
            database_url=str(env.get("DATABASE_URL") or "").strip(),
            postgres_enabled=str(env.get("POSTGRES_RUNTIME_ENABLED") or "").strip().lower() in {"1", "true", "yes", "enabled"},
            migrations_required=str(env.get("MIGRATIONS_REQUIRED") or "1").strip().lower() not in {"0", "false", "no"},
            release_id=str(env.get("RELEASE_ID") or env.get("GITHUB_SHA") or "unknown").strip() or "unknown",
        )


@dataclass(frozen=True)
class ProductionBootCheck:
    name: str
    passed: bool
    reason: str


@dataclass(frozen=True)
class ProductionBootReport:
    status: str
    storage_mode: ProductionStorageMode
    release_id: str
    checks: tuple[ProductionBootCheck, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return self.status == "passed" and all(item.passed for item in self.checks)

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact": "production_boot",
            "passed": self.passed,
            "status": self.status,
            "storage_mode": self.storage_mode.value,
            "release_id": self.release_id,
            "checks": [
                {"name": item.name, "passed": item.passed, "reason": item.reason}
                for item in self.checks
            ],
        }


def _is_postgres_dsn(value: str) -> bool:
    lowered = value.strip().lower()
    return lowered.startswith("postgresql://") or lowered.startswith("postgres://")


def evaluate_production_boot_contract(input_data: ProductionBootInput) -> ProductionBootReport:
    profile = input_data.app_profile or input_data.run_mode
    storage_mode = ProductionStorageMode.POSTGRES_REQUIRED if input_data.postgres_enabled else ProductionStorageMode.SQLITE_DEV
    checks = [
        ProductionBootCheck("env_is_production", input_data.env == "production", "ENV must be production"),
        ProductionBootCheck("profile_is_api", profile == "api", "APP_PROFILE/RUN_MODE must select api profile"),
        ProductionBootCheck("postgres_enabled", input_data.postgres_enabled, "POSTGRES_RUNTIME_ENABLED must be enabled"),
        ProductionBootCheck("database_url_is_postgres", _is_postgres_dsn(input_data.database_url), "DATABASE_URL must be postgres/postgresql DSN"),
        ProductionBootCheck("migrations_required", input_data.migrations_required, "migrations must run before start"),
    ]
    passed = all(item.passed for item in checks)
    return ProductionBootReport(
        status="passed" if passed else "blocked",
        storage_mode=storage_mode,
        release_id=input_data.release_id,
        checks=tuple(checks),
    )


__all__ = [
    "ProductionBootCheck",
    "ProductionBootInput",
    "ProductionBootReport",
    "ProductionStorageMode",
    "evaluate_production_boot_contract",
]
