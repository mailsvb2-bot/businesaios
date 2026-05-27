from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from runtime.platform.business_memory.models import BusinessMemoryRecord

CANON_BUSINESS_MEMORY_STORE = True


@dataclass
class FileBusinessMemoryStore:
    root_dir: Path

    def __post_init__(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _scope_key(*, business_id: str, tenant_id: str | None = None) -> str:
        tenant = str(tenant_id or '').strip()
        business = str(business_id)
        return f"{tenant}__{business}" if tenant else business

    def load(self, *, business_id: str, tenant_id: str | None = None) -> BusinessMemoryRecord:
        target = self.root_dir / f"{self._scope_key(business_id=str(business_id), tenant_id=tenant_id)}.json"
        if not target.exists() and tenant_id is None:
            scoped_matches = sorted(self.root_dir.glob(f"*__{str(business_id)}.json"))
            if len(scoped_matches) == 1:
                target = scoped_matches[0]
        if not target.exists():
            return BusinessMemoryRecord(business_id=str(business_id))
        return BusinessMemoryRecord.from_dict(json.loads(target.read_text(encoding='utf-8')), business_id=str(business_id))

    def save(self, record: BusinessMemoryRecord, *, tenant_id: str | None = None) -> Path:
        target = self.root_dir / f"{self._scope_key(business_id=str(record.business_id), tenant_id=tenant_id)}.json"
        target.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2, sort_keys=True), encoding='utf-8')
        return target
