from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Iterator, Mapping

from core.tenancy.normalization import require_tenant_id


CANON_TENANT_CONTEXT = True


@dataclass(frozen=True)
class TenantRequestContext:
    tenant_id: str
    actor_id: str | None = None
    request_id: str | None = None
    trace_id: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        require_tenant_id(self.tenant_id)
        if self.actor_id is not None and not str(self.actor_id).strip():
            raise ValueError("actor_id must not be blank when provided")
        if self.request_id is not None and not str(self.request_id).strip():
            raise ValueError("request_id must not be blank when provided")
        if self.trace_id is not None and not str(self.trace_id).strip():
            raise ValueError("trace_id must not be blank when provided")


_CURRENT_TENANT_CONTEXT: ContextVar[TenantRequestContext | None] = ContextVar(
    "tenant_request_context",
    default=None,
)


def current_tenant_context() -> TenantRequestContext | None:
    return _CURRENT_TENANT_CONTEXT.get()


def get_current_tenant_id(*, require: bool = False) -> str:
    ctx = current_tenant_context()
    tenant_id = str(getattr(ctx, "tenant_id", "") or "")
    if require:
        return require_tenant_id(tenant_id)
    return tenant_id.strip()


def set_current_tenant_context(
    context: TenantRequestContext | None,
) -> Token[TenantRequestContext | None]:
    if context is not None:
        context.validate()
    return _CURRENT_TENANT_CONTEXT.set(context)


def reset_current_tenant_context(token: Token[TenantRequestContext | None]) -> None:
    _CURRENT_TENANT_CONTEXT.reset(token)


@contextmanager
def bind_tenant_context(context: TenantRequestContext) -> Iterator[TenantRequestContext]:
    context.validate()
    token = set_current_tenant_context(context)
    try:
        yield context
    finally:
        reset_current_tenant_context(token)


@contextmanager
def bind_tenant_id(tenant_id: str, **metadata: object) -> Iterator[TenantRequestContext]:
    ctx = TenantRequestContext(
        tenant_id=require_tenant_id(tenant_id),
        metadata=dict(metadata),
    )
    with bind_tenant_context(ctx) as bound:
        yield bound


__all__ = [
    "CANON_TENANT_CONTEXT",
    "TenantRequestContext",
    "bind_tenant_context",
    "bind_tenant_id",
    "current_tenant_context",
    "get_current_tenant_id",
    "reset_current_tenant_context",
    "set_current_tenant_context",
]
