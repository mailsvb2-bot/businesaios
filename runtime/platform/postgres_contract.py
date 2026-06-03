from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from collections.abc import Mapping

from runtime.execution.crash_window_recovery_contract import CrashWindowRecoveryAction


class PostgresContractStatus(str, Enum):
    READY = "ready"
    BLOCKED = "blocked"
    ADVISORY_ONLY = "advisory_only"


# Logical runtime storage requirements. Each tuple accepts either the canonical
# contract table name or a real adapter table name. This prevents production
# readiness checks from drifting away from the actual Postgres adapters.
REQUIRED_SCHEMA_OBJECT_ALIASES: Mapping[str, tuple[str, ...]] = {
    "events": ("events",),
    "runtime_outbox": ("runtime_outbox", "outbox"),
    "payment_outbox": ("payment_outbox",),
    "decision_archive": ("decision_archive",),
    "evidence_archive": ("evidence_archive",),
    "runtime_snapshots": ("runtime_snapshots", "snapshots"),
    "execution_ledger": ("execution_ledger", "executed", "executed_chain"),
    "recovery_queue": ("recovery_queue",),
}

REQUIRED_SCHEMA_OBJECTS = tuple(REQUIRED_SCHEMA_OBJECT_ALIASES)

REQUIRED_MIGRATIONS = (
    "events_v1",
    "runtime_outbox_v1",
    "decision_archive_v1",
    "evidence_archive_v1",
    "execution_ledger_v1",
    "recovery_queue_v1",
)


@dataclass(frozen=True)
class PostgresRuntimeProof:
    database_url_present: bool
    postgres_enabled: bool
    psycopg_available: bool
    live_probe_ok: bool
    schema_objects_present: tuple[str, ...]
    migrations_applied: tuple[str, ...]
    event_store_roundtrip_ok: bool
    outbox_roundtrip_ok: bool
    recovery_contract_ok: bool

    @classmethod
    def advisory(cls) -> PostgresRuntimeProof:
        return cls(
            database_url_present=False,
            postgres_enabled=False,
            psycopg_available=False,
            live_probe_ok=False,
            schema_objects_present=(),
            migrations_applied=(),
            event_store_roundtrip_ok=False,
            outbox_roundtrip_ok=False,
            recovery_contract_ok=True,
        )


def _missing(required: tuple[str, ...], present: tuple[str, ...]) -> list[str]:
    present_set = set(present)
    return [item for item in required if item not in present_set]


def _missing_logical_schema(present: tuple[str, ...]) -> list[str]:
    present_set = set(present)
    missing: list[str] = []
    for logical_name, aliases in REQUIRED_SCHEMA_OBJECT_ALIASES.items():
        if not any(alias in present_set for alias in aliases):
            missing.append(logical_name)
    return missing


def _schema_alias_status(present: tuple[str, ...]) -> dict[str, object]:
    present_set = set(present)
    return {
        logical_name: {
            "accepted": [alias for alias in aliases if alias in present_set],
            "aliases": list(aliases),
        }
        for logical_name, aliases in REQUIRED_SCHEMA_OBJECT_ALIASES.items()
    }


def evaluate_postgres_contract(proof: PostgresRuntimeProof) -> dict[str, object]:
    violations: list[str] = []
    warnings: list[str] = []
    if not proof.database_url_present and not proof.postgres_enabled:
        warnings.append("postgres_runtime_not_declared")
    else:
        if not proof.database_url_present:
            violations.append("database_url_required")
        if not proof.postgres_enabled:
            violations.append("postgres_enablement_required")
        if not proof.psycopg_available:
            violations.append("psycopg_runtime_required")
        if not proof.live_probe_ok:
            violations.append("postgres_live_probe_required")
        missing_schema = _missing_logical_schema(proof.schema_objects_present)
        missing_migrations = _missing(REQUIRED_MIGRATIONS, proof.migrations_applied)
        if missing_schema:
            violations.append("postgres_schema_objects_missing:" + ",".join(missing_schema))
        if missing_migrations:
            violations.append("postgres_migrations_missing:" + ",".join(missing_migrations))
        if not proof.event_store_roundtrip_ok:
            violations.append("postgres_event_store_roundtrip_required")
        if not proof.outbox_roundtrip_ok:
            violations.append("postgres_outbox_roundtrip_required")
        if not proof.recovery_contract_ok:
            violations.append("postgres_recovery_contract_required")
    status = (
        PostgresContractStatus.ADVISORY_ONLY.value
        if warnings and not violations
        else PostgresContractStatus.BLOCKED.value
        if violations
        else PostgresContractStatus.READY.value
    )
    return {
        "artifact": "postgres_contract",
        "status": status,
        "database_url_present": proof.database_url_present,
        "postgres_enabled": proof.postgres_enabled,
        "psycopg_available": proof.psycopg_available,
        "live_probe_ok": proof.live_probe_ok,
        "schema_objects_present": list(proof.schema_objects_present),
        "required_schema_objects": list(REQUIRED_SCHEMA_OBJECTS),
        "required_schema_object_aliases": {key: list(value) for key, value in REQUIRED_SCHEMA_OBJECT_ALIASES.items()},
        "schema_alias_status": _schema_alias_status(proof.schema_objects_present),
        "migrations_applied": list(proof.migrations_applied),
        "required_migrations": list(REQUIRED_MIGRATIONS),
        "event_store_roundtrip_ok": proof.event_store_roundtrip_ok,
        "outbox_roundtrip_ok": proof.outbox_roundtrip_ok,
        "recovery_contract_ok": proof.recovery_contract_ok,
        "required_recovery_action": CrashWindowRecoveryAction.REPLAY_DISPATCH.value,
        "violations": violations,
        "warnings": warnings,
        "claims_production_ready": False,
    }


__all__ = [
    "PostgresContractStatus",
    "PostgresRuntimeProof",
    "REQUIRED_MIGRATIONS",
    "REQUIRED_SCHEMA_OBJECT_ALIASES",
    "REQUIRED_SCHEMA_OBJECTS",
    "evaluate_postgres_contract",
]
