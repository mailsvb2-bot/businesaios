from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional, Protocol
from collections.abc import Iterable

from core.tenancy.scope import TenantId


@dataclass(frozen=True)
class DataExportRequest:
    tenant_id: TenantId
    user_id: str
    start_ms: int = 0
    end_ms: int | None = None


@dataclass(frozen=True)
class DataDeleteRequest:
    tenant_id: TenantId
    user_id: str
    reason: str = "user_request"
    requested_at_ms: int = 0


class UserDataSource(Protocol):
    """A user-data source that supports export and/or delete."""

    def export(self, req: DataExportRequest) -> Iterable[dict[str, Any]]: ...

    def delete(self, req: DataDeleteRequest) -> int: ...


class DataRightsService:
    """Orchestrates export/delete across registered sources.

    Design:
      - sources are small dumb adapters (event store, snapshots, payment outbox, etc.)
      - this service does orchestration only (no storage details)
    """

    def __init__(self, *, sources: dict[str, UserDataSource]):
        self._sources = dict(sources)

    def export_user(self, req: DataExportRequest) -> dict[str, Any]:
        uid = (req.user_id or "").strip()
        if not uid:
            raise ValueError("EMPTY_USER_ID")
        out: dict[str, Any] = {"tenant_id": str(req.tenant_id), "user_id": uid, "sources": {}}
        for name, src in self._sources.items():
            items = list(src.export(req))
            out["sources"][name] = {"count": len(items), "items": items}
        return out

    def delete_user(self, req: DataDeleteRequest) -> dict[str, Any]:
        uid = (req.user_id or "").strip()
        if not uid:
            raise ValueError("EMPTY_USER_ID")
        at = int(req.requested_at_ms or 0) or int(time.time() * 1000)
        req2 = DataDeleteRequest(
            tenant_id=req.tenant_id,
            user_id=uid,
            reason=(req.reason or "user_request").strip()[:100],
            requested_at_ms=at,
        )
        res: dict[str, Any] = {"tenant_id": str(req2.tenant_id), "user_id": uid, "deleted": {}}
        total = 0
        for name, src in self._sources.items():
            n = int(src.delete(req2))
            res["deleted"][name] = n
            total += n
        res["deleted_total"] = total
        return res
