from __future__ import annotations

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager

_IN_EXECUTOR: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "runtime.executor._IN_EXECUTOR",
    default=False,
)
_EXECUTION_BUSINESS_ID: contextvars.ContextVar[str] = contextvars.ContextVar(
    "runtime.executor._EXECUTION_BUSINESS_ID",
    default="",
)


def is_executor_context_active() -> bool:
    return bool(_IN_EXECUTOR.get())


def assert_called_from_executor(why: str = "SIDE_EFFECT_REQUIRES_EXECUTOR") -> None:
    if not is_executor_context_active():
        raise RuntimeError(why)


def current_execution_business_id() -> str:
    return str(_EXECUTION_BUSINESS_ID.get() or "").strip()


@contextmanager
def execution_business_scope(business_id: str | None) -> Iterator[None]:
    token = _EXECUTION_BUSINESS_ID.set(str(business_id or "").strip())
    try:
        yield
    finally:
        _EXECUTION_BUSINESS_ID.reset(token)


@contextmanager
def executor_context(name: str = "runtime_executor") -> Iterator[None]:
    _ = name
    token = _IN_EXECUTOR.set(True)
    try:
        yield
    finally:
        _IN_EXECUTOR.reset(token)


__all__ = ["is_executor_context_active", "assert_called_from_executor", "current_execution_business_id", "execution_business_scope", "executor_context"]
