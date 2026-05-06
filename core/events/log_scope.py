from __future__ import annotations


def resolve_ctx_tenant_id(ctx) -> str:
    tid = getattr(ctx, "tenant_id", None) or getattr(getattr(ctx, "boot", None), "tenant_id", None)
    return str(tid or "").strip()


def ensure_ctx_matches_event_log(*, ctx, tenant_id: str) -> None:
    ctx_tenant_id = resolve_ctx_tenant_id(ctx)
    if ctx_tenant_id and ctx_tenant_id != str(tenant_id):
        raise ValueError("ctx tenant_id mismatch with EventLog tenant scope")
