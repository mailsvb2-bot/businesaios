from __future__ import annotations

from core.ads.apply.audit import build_audit_event
from core.ads.apply.contract import AdsApplyResult


def blocked_result(*, tenant_id: str, user_id: str, kind: str, plan, idem_norm: str, reason: str, code: str, detail: dict) -> AdsApplyResult:
    ev = build_audit_event(
        tenant_id=tenant_id,
        user_id=user_id,
        kind=kind,
        plan=plan,
        status="blocked",
        detail=detail,
        idempotency_key=idem_norm,
        reason=reason,
        error_code=code,
    )
    return AdsApplyResult(status="blocked", detail={"error": code}, audit_event=ev)
