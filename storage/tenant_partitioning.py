from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re

from core.tenancy.normalization import normalize_tenant_id, require_tenant_id


CANON_STORAGE_TENANT_PARTITIONING = True
_MAX_IDENTIFIER_LEN = 48
_NON_ALNUM = re.compile(r"[^a-z0-9_]+")


@dataclass(frozen=True)
class TenantPartition:
    tenant_id: str
    partition_key: str
    partition_suffix: str
    postgres_schema: str
    label: str


def _slug(value: str) -> str:
    normalized = _NON_ALNUM.sub("_", str(value or "").strip().lower()).strip("_")
    return normalized or "global"


def normalize_storage_tenant_id(tenant_id: str | None) -> str:
    normalized = normalize_tenant_id(tenant_id)
    return normalized or "global"


def partition_suffix(tenant_id: str | None) -> str:
    normalized = normalize_storage_tenant_id(tenant_id)
    if normalized == "global":
        return "global"
    strict = require_tenant_id(normalized)
    slug = _slug(strict)
    digest = hashlib.sha1(strict.encode("utf-8")).hexdigest()[:12]
    base = f"{slug}_{digest}"
    return base[:_MAX_IDENTIFIER_LEN].rstrip("_") or "global"


def postgres_schema_name(tenant_id: str | None, *, prefix: str = "tenant") -> str:
    prefix_slug = _slug(prefix)
    suffix = partition_suffix(tenant_id)
    schema = f"{prefix_slug}_{suffix}"
    return schema[:63].rstrip("_") or "tenant_global"


def build_partition_key(tenant_id: str | None, *, scope: str = "default") -> str:
    normalized_scope = _slug(scope)
    normalized_tenant_id = normalize_storage_tenant_id(tenant_id)
    return f"{normalized_scope}:{normalized_tenant_id}"


def partition_label(tenant_id: str | None, *, scope: str = "default") -> str:
    return f"{_slug(scope)}::{normalize_storage_tenant_id(tenant_id)}"


def describe_tenant_partition(tenant_id: str | None, *, scope: str = "default", prefix: str = "tenant") -> TenantPartition:
    normalized = normalize_storage_tenant_id(tenant_id)
    return TenantPartition(
        tenant_id=normalized,
        partition_key=build_partition_key(normalized, scope=scope),
        partition_suffix=partition_suffix(normalized),
        postgres_schema=postgres_schema_name(normalized, prefix=prefix),
        label=partition_label(normalized, scope=scope),
    )


__all__ = [
    "CANON_STORAGE_TENANT_PARTITIONING",
    "TenantPartition",
    "build_partition_key",
    "describe_tenant_partition",
    "normalize_storage_tenant_id",
    "partition_label",
    "partition_suffix",
    "postgres_schema_name",
]
