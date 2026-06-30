"""Request-scoped tenant context (SaaS-first).

Goal:
  tenant must be bound to *request/session/token*, not to process.

This module provides a tiny, explicit primitive based on contextvars.
It is safe to import from any layer.

Fallback behavior:
  If a request has not bound a tenant explicitly, we fallback to the
  process tenant (TENANT_ID env) via core.tenancy.tenant.current_tenant_id().
  This keeps legacy flows working while enabling SaaS-first flows.
"""

from __future__ import annotations


from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from collections.abc import Iterator

from core.tenancy.scope import TenantId, as_tenant_id
from core.tenancy.tenant import current_tenant_id

_tenant_var: ContextVar[TenantId | None] = ContextVar("tenant_id", default=None)


@dataclass(frozen=True)
class TenantContext:
    tenant_id: TenantId
    token: Token[TenantId | None] | None = None


def bind_tenant(tenant_id: str | TenantId) -> TenantContext:
    tid = as_tenant_id(tenant_id)
    token = _tenant_var.set(tid)
    return TenantContext(tenant_id=tid, token=token)


def reset_tenant(context: TenantContext | Token[TenantId | None] | None) -> None:
    if context is None:
        return
    token = context if isinstance(context, Token) else context.token
    if token is not None:
        _tenant_var.reset(token)


@contextmanager
def tenant_scope(tenant_id: str | TenantId) -> Iterator[TenantId]:
    ctx = bind_tenant(tenant_id)
    try:
        yield ctx.tenant_id
    finally:
        reset_tenant(ctx)


def get_tenant_id() -> TenantId:
    v = _tenant_var.get()
    if v is not None:
        return v
    return as_tenant_id(current_tenant_id())


def maybe_tenant_id() -> TenantId | None:
    return _tenant_var.get()


class TenantRequired(RuntimeError):
    pass


def require_tenant_id() -> TenantId:
    tid = get_tenant_id()
    if not str(tid or "").strip():
        raise TenantRequired("TENANT_REQUIRED")
    return tid
