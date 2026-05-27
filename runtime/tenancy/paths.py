from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from runtime.tenancy import require_tenant_id


@dataclass(frozen=True)
class TenantPaths:
    """Filesystem paths for a tenant.

    Canon: all tenant-scoped durable artifacts live under one data_root.
    """

    tenant_id: str
    base_root: Path  # e.g. <repo>/runtime/data  OR an operator-provided DATA_DIR

    @property
    def data_root(self) -> Path:
        tid = require_tenant_id(self.tenant_id)
        p = (self.base_root / tid).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    def db_path(self, name: str) -> Path:
        return self.data_root / f"{name}.db"

    def lock_path(self, name: str) -> Path:
        return self.data_root / f"{name}.lock"
