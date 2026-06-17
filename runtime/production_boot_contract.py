from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum


class ProductionBootStatus(str, Enum):
    CONTRACT_SATISFIED = "contract_satisfied"
    BLOCKED = "blocked"
    ADVISORY_ONLY = "advisory_only"


_PLACEHOLDER_MARKERS = (
    "change-me",
    "replace_with",
    "placeholder",
    "example",
    "dummy",
    "todo",
)


def _env_key(*parts: str) -> str:
    return "_".join(str(part).strip() for part in parts if str(part).strip())


@dataclass(frozen=True)
class ProductionBootProbe:
    env: str
    app_profile: str
    database_url_present: bool
    postgres_enabled: bool
    migrations_required: bool
    release_quality_tools_required: bool
    database_url_placeholder: bool = False
    telegram_token_placeholder: bool = False
    webhook_secret_placeholder: bool = False
    control_plane_key_placeholder: bool = False
    secret_backend_placeholder: bool = False
    key_provider_placeholder: bool = False
    sqlite_secret_backend_in_prod: bool = False
    sqlite_key_provider_in_prod: bool = False

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> ProductionBootProbe:
        runtime_env = str(env.get("ENV") or env.get("APP_ENV") or "ci").strip().lower() or "ci"
        profile = str(env.get("APP_PROFILE") or env.get("RUN_MODE") or "api").strip().lower() or "api"
        database_url = str(env.get("DATABASE_URL") or env.get("POSTGRES_DSN") or "").strip()
        postgres_enabled = str(
            env.get("POSTGRES_RUNTIME_ENABLED") or env.get("POSTGRES_EVENT_STORE_ENABLED") or env.get("METRO_DB_ENGINE") or ""
        ).strip().lower() in {"1", "true", "yes", "enabled", "postgres", "postgresql"}
        migrations_required = str(
            env.get("MIGRATIONS_REQUIRED") or env.get("RUN_MIGRATIONS_BEFORE_START") or "1"
        ).strip().lower() not in {"0", "false", "no", "disabled"}
        release_quality = str(env.get("BAIOS_REQUIRE_QUALITY_TOOLS") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "release",
        }
        secret_backend = str(env.get("BUSINESAIOS_SECRET_VAULT_BACKEND") or "").strip()
        key_provider = str(env.get("BUSINESAIOS_KEY_PROVIDER_BACKEND") or "").strip()
        telegram_token = str(env.get(_env_key("TELEGRAM", "BOT", "TOKEN")) or "")
        return cls(
            env=runtime_env,
            app_profile=profile,
            database_url_present=bool(database_url),
            postgres_enabled=postgres_enabled,
            migrations_required=migrations_required,
            release_quality_tools_required=release_quality,
            database_url_placeholder=_looks_placeholder(database_url),
            telegram_token_placeholder=_looks_placeholder(telegram_token),
            webhook_secret_placeholder=_looks_placeholder(str(env.get("TELEGRAM_WEBHOOK_SECRET") or "")),
            control_plane_key_placeholder=_looks_placeholder(str(env.get("CONTROL_PLANE_API_KEY") or "")),
            secret_backend_placeholder=_looks_placeholder(secret_backend),
            key_provider_placeholder=_looks_placeholder(key_provider),
            sqlite_secret_backend_in_prod=secret_backend.lower() == "sqlite",
            sqlite_key_provider_in_prod=key_provider.lower() == "sqlite",
        )


def _looks_placeholder(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return False
    return any(marker in normalized for marker in _PLACEHOLDER_MARKERS)


def evaluate_production_boot(probe: ProductionBootProbe) -> dict[str, object]:
    is_production = probe.env in {"prod", "production"}
    violations: list[str] = []
    warnings: list[str] = []
    if probe.app_profile not in {"api", "worker", "evolution", "telegram", "webhook"}:
        violations.append("unsupported_app_profile")
    if is_production:
        if not probe.database_url_present:
            violations.append("production_database_url_required")
        if probe.database_url_placeholder:
            violations.append("production_database_url_placeholder_forbidden")
        if not probe.postgres_enabled:
            violations.append("production_postgres_enablement_required")
        if not probe.migrations_required:
            violations.append("production_migrations_must_run_before_start")
        if not probe.release_quality_tools_required:
            warnings.append("release_quality_tools_not_required_in_env")
        if probe.telegram_token_placeholder:
            violations.append("production_telegram_token_placeholder_forbidden")
        if probe.webhook_secret_placeholder:
            violations.append("production_webhook_secret_placeholder_forbidden")
        if probe.control_plane_key_placeholder:
            violations.append("production_control_plane_key_placeholder_forbidden")
        if probe.secret_backend_placeholder:
            violations.append("production_secret_backend_placeholder_forbidden")
        if probe.key_provider_placeholder:
            violations.append("production_key_provider_placeholder_forbidden")
        if probe.sqlite_secret_backend_in_prod:
            violations.append("production_sqlite_secret_backend_forbidden")
        if probe.sqlite_key_provider_in_prod:
            violations.append("production_sqlite_key_provider_forbidden")
    else:
        warnings.append("non_production_profile_advisory_only")
    production_contract_satisfied = is_production and not violations
    status = (
        ProductionBootStatus.CONTRACT_SATISFIED.value
        if production_contract_satisfied
        else ProductionBootStatus.BLOCKED.value
        if violations
        else ProductionBootStatus.ADVISORY_ONLY.value
    )
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
        "database_url_placeholder": probe.database_url_placeholder,
        "telegram_token_placeholder": probe.telegram_token_placeholder,
        "webhook_secret_placeholder": probe.webhook_secret_placeholder,
        "control_plane_key_placeholder": probe.control_plane_key_placeholder,
        "secret_backend_placeholder": probe.secret_backend_placeholder,
        "key_provider_placeholder": probe.key_provider_placeholder,
        "sqlite_secret_backend_in_prod": probe.sqlite_secret_backend_in_prod,
        "sqlite_key_provider_in_prod": probe.sqlite_key_provider_in_prod,
        "violations": violations,
        "warnings": warnings,
        "production_boot_contract_satisfied": production_contract_satisfied,
        "requires_live_postgres_probe": production_contract_satisfied,
        "requires_container_runtime_probe": production_contract_satisfied,
        "claims_production_ready": False,
    }


def assert_production_boot_ready(probe: ProductionBootProbe) -> None:
    report = evaluate_production_boot(probe)
    if report["status"] != ProductionBootStatus.CONTRACT_SATISFIED.value:
        raise RuntimeError("PRODUCTION_BOOT_NOT_READY:" + ",".join(report["violations"] or report["warnings"]))


__all__ = ["ProductionBootProbe", "ProductionBootStatus", "assert_production_boot_ready", "evaluate_production_boot"]
