from __future__ import annotations

from dataclasses import dataclass

from core.tenancy.normalization import require_tenant_id


CANON_TENANT_MEMORY_SCOPE = True


@dataclass(frozen=True)
class TenantMemoryScope:
    tenant_id: str
    namespace_prefixes: tuple[str, ...] = ("default",)
    retention_days: int = 365
    max_records: int = 100_000
    max_bytes: int = 256 * 1024 * 1024
    allow_cross_business_reads: bool = False

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if int(self.retention_days) < 1:
            raise ValueError("retention_days must be >= 1")
        if int(self.max_records) < 1:
            raise ValueError("max_records must be >= 1")
        if int(self.max_bytes) < 1:
            raise ValueError("max_bytes must be >= 1")
        cleaned = [str(item or "").strip() for item in self.namespace_prefixes]
        if not cleaned or any(not item for item in cleaned):
            raise ValueError(
                "namespace_prefixes must contain at least one non-empty prefix"
            )

    def allows_namespace(self, namespace: str) -> bool:
        self.validate()
        value = str(namespace or "").strip()
        if not value:
            return False
        return any(
            value == prefix or value.startswith(prefix + "/")
            for prefix in self.namespace_prefixes
        )

    def qualify_namespace(self, *, business_id: str, namespace: str) -> str:
        self.validate()
        if not str(business_id or "").strip():
            raise ValueError("business_id is required")
        if not self.allows_namespace(namespace):
            raise ValueError(
                f"namespace not allowed for tenant={self.tenant_id}: {namespace}"
            )
        return (
            f"tenant/{self.tenant_id}/business/{str(business_id).strip()}/"
            f"{str(namespace).strip()}"
        )


__all__ = ["CANON_TENANT_MEMORY_SCOPE", "TenantMemoryScope"]
