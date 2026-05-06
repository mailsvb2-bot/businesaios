from __future__ import annotations
CANON_BOOT_ENTRYPOINT_CONTEXT_FINAL_OWNER = True


from contextlib import contextmanager
from contextvars import ContextVar
from collections.abc import Iterator


CANON_BOOT_ENTRYPOINT_CONTEXT = True

_ALLOWED_BOOTSTRAP_ENTRYPOINTS = frozenset({"main", "headless_cli", "headless_sdk", "test"})
_ACTIVE_BOOTSTRAP_ENTRYPOINT: ContextVar[tuple[str, ...]] = ContextVar(
    "ACTIVE_BOOTSTRAP_ENTRYPOINT",
    default=(),
)


def is_allowed_bootstrap_entrypoint(name: str) -> bool:
    return str(name).strip() in _ALLOWED_BOOTSTRAP_ENTRYPOINTS


def current_bootstrap_entrypoint() -> str | None:
    stack = _ACTIVE_BOOTSTRAP_ENTRYPOINT.get()
    return stack[-1] if stack else None


def is_bootstrap_entrypoint_active(name: str | None = None) -> bool:
    current = current_bootstrap_entrypoint()
    if current is None:
        return False
    if name is None:
        return True
    return current == str(name).strip()


@contextmanager
def bootstrap_entrypoint(entrypoint_name: str) -> Iterator[str]:
    name = str(entrypoint_name).strip()
    if not is_allowed_bootstrap_entrypoint(name):
        raise ValueError(f"UNKNOWN_BOOTSTRAP_ENTRYPOINT:{name}")
    current = _ACTIVE_BOOTSTRAP_ENTRYPOINT.get()
    token = _ACTIVE_BOOTSTRAP_ENTRYPOINT.set((*current, name))
    try:
        yield name
    finally:
        _ACTIVE_BOOTSTRAP_ENTRYPOINT.reset(token)


__all__ = [
    "CANON_BOOT_ENTRYPOINT_CONTEXT",
    "bootstrap_entrypoint",
    "current_bootstrap_entrypoint",
    "is_allowed_bootstrap_entrypoint",
    "is_bootstrap_entrypoint_active",
]
