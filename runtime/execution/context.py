from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Iterator

_IN_EXECUTOR: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "runtime.executor._IN_EXECUTOR",
    default=False,
)


def is_executor_context_active() -> bool:
    return bool(_IN_EXECUTOR.get())


def assert_called_from_executor(why: str = "SIDE_EFFECT_REQUIRES_EXECUTOR") -> None:
    if not is_executor_context_active():
        raise RuntimeError(why)


@contextmanager
def executor_context(name: str = "runtime_executor") -> Iterator[None]:
    _ = name
    token = _IN_EXECUTOR.set(True)
    try:
        yield
    finally:
        _IN_EXECUTOR.reset(token)


__all__ = ["is_executor_context_active", "assert_called_from_executor", "executor_context"]
