from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from core.api.idempotency import IdempotencyKey
from core.tenancy.scope import TenantId

Json = Dict[str, Any]


@dataclass(frozen=True)
class AdsApplyRequest:
    tenant_id: TenantId
    user_id: str
    plan: Any  # core.ads.ads_service.AdsPlan (kept Any to avoid import cycles)
    idempotency: IdempotencyKey
    dry_run: bool = True
    rollback_on_fail: bool = True
    reason: str = "manual"


@dataclass(frozen=True)
class AdsApplyResult:
    status: str  # "dry_run" | "applied" | "skipped" | "duplicate" | "blocked" | "failed"
    detail: Json
    audit_event: Optional[Json] = None
