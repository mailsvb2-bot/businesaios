from __future__ import annotations

from storage.audit_store import AuditRecord, InMemoryAuditStore, PostgresAuditStore, SqliteAuditStore
from storage.evidence_store import EvidenceRecord, InMemoryEvidenceStore, PostgresEvidenceStore, SqliteEvidenceStore
from storage.inference_execution_record_repository import InferenceExecutionRecordRepository
from storage.migration_registry import Migration, MigrationRegistry, default_storage_migration_registry
from storage.postgres_session import PostgresSession, PostgresSessionFactory
from storage.retention_jobs import RetentionJobReport, RetentionPolicy, StorageRetentionJobRunner
from storage.schema_version_store import (
    InMemorySchemaVersionStore,
    PostgresSchemaVersionStore,
    SchemaVersionRecord,
    SqliteSchemaVersionStore,
)
from storage.sqlite_fallback import SqliteSession, SqliteSessionFactory
from storage.tenant_partitioning import (
    TenantPartition,
    build_partition_key,
    describe_tenant_partition,
    normalize_storage_tenant_id,
    partition_label,
    partition_suffix,
    postgres_schema_name,
)

CANON_STORAGE_NAMESPACE = True
CANON_STORAGE_PACKAGE_OWNER = True

__all__ = [
    "AuditRecord",
    "CANON_STORAGE_NAMESPACE",
    "CANON_STORAGE_PACKAGE_OWNER",
    "EvidenceRecord",
    "InMemoryAuditStore",
    "InMemoryEvidenceStore",
    "InferenceExecutionRecordRepository",
    "InMemorySchemaVersionStore",
    "Migration",
    "MigrationRegistry",
    "PostgresAuditStore",
    "PostgresEvidenceStore",
    "PostgresSchemaVersionStore",
    "PostgresSession",
    "PostgresSessionFactory",
    "RetentionJobReport",
    "RetentionPolicy",
    "SchemaVersionRecord",
    "SqliteAuditStore",
    "SqliteEvidenceStore",
    "SqliteSchemaVersionStore",
    "SqliteSession",
    "SqliteSessionFactory",
    "StorageRetentionJobRunner",
    "TenantPartition",
    "build_partition_key",
    "default_storage_migration_registry",
    "describe_tenant_partition",
    "normalize_storage_tenant_id",
    "partition_label",
    "partition_suffix",
    "postgres_schema_name",
]
