from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class ProductionBootStatus(str, Enum):
    READY = "ready"
    BLOCKED = "blocked"
    ADVISORY_ONLY = "advisory_only"


@dataclass(frozen=True)
class ProductionBootProbe:
    env: str
    app_profile: str
    database_url_present: bool
    postgres_enabled: bool
    migrations_required: bool
    release_quality_tools_required: bool

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "ProductionBootProbe":
        runtime_env = str(env.get("ENV") or env.get("APP_ENV") or "ci").strip().lower() or "ci"
        profile = str(env.get("APP_PROFILE") or env.get("RUN_MODE") or "api").strip().lower() or "api"
        database_url = str(env.get("DATABASE_URL") or env.get("POSTGRES_DSN") or "").strip()
        postgres_enabled = str(env.get("POSTGRES_RUNTIME_ENABLED") or env.get("POSTGRES_EVENT_STORE_ENABLED") or "").strip().lower() in {"1", "true", "yes", "enabled"}
        migrations_required = str(env.get("MIGRATIONS_REQUIRED") or env.get("RUN_MIGRATIONS_BEFORE_START") or "1").strip().lower() not in {"0", "false", "no", "disabled"}
        release_quality = str(env.get("BAIOS_REQUIRE_QUALITY_TOOLS") or "").strip().lower() in {"1", "true", "yes", "release"}
        return cls(
            env=runtime_env,
            app_profile=profile,
            database_url_present=bool(database_url),
            postgres_enabled=postgres_enabled,
            migrations_required=migrations_required,
            release_quality_tools_required=release_quality,
        )


def evaluate_production_boot(probe: ProductionBootProbe) -> dict[str, object]:
    is_production = probe.env in {"prod", "production"}
    violations: list[str] = []
    warnings: list[str] = []
    if probe.app_profile not in {"api", "worker", "evolution", "telegram", "webhook"}:
        violations.append("unsupported_app_profile")
    if is_production:
        if not probe.database_url_present:
            violations.append("production_database_url_required")
        if not probe.postgres_enabled:
            violations.append("production_postgres_enablement_required")
        if not probe.migrations_required:
            violations.append("production_migrations_must_run_before_start")
        if not probe.release_quality_tools_required:
            warnings.append("release_quality_tools_not_required_in_env")
    else:
        warnings.append("non_production_profile_advisory_only")
    status = ProductionBootStatus.READY.value if not violations and is_production else ProductionBootStatus.BLOCKED.value if violations else ProductionBootStatus.ADVISORY_ONLY.value
    return {
        "artifact": "production_boot",
        "status": status,
        "production_profile": is_production,
        "env": probe.env,
        "app_profile": probe.app_profile,
        "database_url_present": probe.database_url_present,
        "postgres_enabled": probe.postgres_enabled,
        "migrations_required": probe.migrations_required,
        "release_quality_tools_required": probe.release_quality_tools_required,
        "violations": violations,
        "warnings": warnings,
        "claims_production_ready": status == ProductionBootStatus.READY.value,
    }


def assert_production_boot_ready(probe: ProductionBootProbe) -> None:
    report = evaluate_production_boot(probe)
    if report["status"] != ProductionBootStatus.READY.value:
        raise RuntimeError("PRODUCTION_BOOT_NOT_READY:" + ",".join(report["violations"] or report["warnings"]))


__all__ = ["ProductionBootProbe", "ProductionBootStatus", "assert_production_boot_ready", "evaluate_production_boot"]
