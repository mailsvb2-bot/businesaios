"""Runtime import firewall for sealed integration internals.

This guard prevents production code from importing sealed internal integration
modules directly. Only the canonical executor/handler surfaces may cross this
boundary. The goal is to keep external effects routed through typed actions,
verified receipts, audit logs and runtime handlers.
"""

from __future__ import annotations

import builtins
import importlib
import os
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from types import FrameType, ModuleType

FORBIDDEN_PREFIXES = (
    "interfaces.payment.yookassa",
    "interfaces.telegram.bot",
    "interfaces.whatsapp.client",
    "interfaces.vk.client",
    "interfaces.max.client",
    "interfaces.ads.meta_connector",
    "interfaces.ads.tiktok_ads_connector",
    "runtime._internal.effects_",
    "runtime._internal.http_transport",
)

ALLOWED_CALLERS = {
    "runtime.effect_router",
    "runtime.executor",
    "runtime.executor_actions",
    "runtime.execution.effect_handler_registry",
    "runtime.execution.action_handler_registry",
    "runtime.handlers",
    "runtime.recovery",
    "runtime.effect_registry",
    "runtime.startup",
    "tests.test_runtime_import_firewall",
}

FORBIDDEN_MODULE_PREFIXES = FORBIDDEN_PREFIXES


def _env_enabled() -> bool:
    return os.getenv("BUSINESAIOS_DISABLE_IMPORT_FIREWALL") not in {"1", "true", "True"}


_original_import = builtins.__import__
_token: ContextVar[bool] = ContextVar("runtime_integration_import_allowed", default=False)


def _next_caller_frame(frame: FrameType | None) -> FrameType | None:
    while frame is not None:
        module = str(frame.f_globals.get("__name__", "") or "")
        if module and module != __name__:
            return frame
        frame = frame.f_back
    return None


def _infer_caller_module() -> str:
    try:
        # Hot import-path guard: avoid inspect.stack(), which resolves source files
        # and can make boot-smoke crawl through large import graphs.
        frame = sys._getframe(2)
        caller = _next_caller_frame(frame)
        if caller is None:
            return ""
        return str(caller.f_globals.get("__name__", "") or "")
    except Exception:
        return ""


def _is_forbidden(name: str) -> bool:
    return any(str(name).startswith(prefix) for prefix in FORBIDDEN_PREFIXES)


def _is_test_caller(caller: str) -> bool:
    return bool(caller.startswith("tests.") or caller.startswith("test_") or ".tests." in caller)


def _allow_forbidden(name: str, caller: str) -> bool:
    if not _env_enabled():
        return True
    if _token.get():
        return True
    if not caller:
        return False
    if str(name).startswith("runtime._internal"):
        # runtime._internal modules may import their own package siblings.
        if caller.startswith("runtime._internal"):
            return True
        # Test modules and pytest helpers are allowed to inspect sealed internals
        # directly; production code remains constrained by static architecture
        # tests and executor-only runtime import windows.
        if _is_test_caller(caller):
            return True
        # Best-effort fallback: allow if we can identify canonical caller.
        return caller in ALLOWED_CALLERS
    # All other forbidden prefixes are never allowed here (they must be accessed via Effects).
    return False


def guarded_import(name, *args, **kwargs):
    # __import__(name, globals=None, locals=None, fromlist=(), level=0)
    caller = _infer_caller_module()
    if _is_forbidden(name) and not _allow_forbidden(name, caller):
        raise ImportError(f"[FIREWALL] Forbidden integration import: {name} by {caller}")
    try:
        return _original_import(name, *args, **kwargs)
    except ModuleNotFoundError as exc:
        if str(name).startswith("runtime._internal"):
            raise ImportError(f"[FIREWALL] Runtime internal import failed (sealed boundary): {name}") from exc
        raise


def install_import_firewall() -> None:
    if not _env_enabled():
        return
    if getattr(builtins.__import__, "__name__", "") == "guarded_import":
        return
    builtins.__import__ = guarded_import


def deactivate_import_firewall() -> None:
    if builtins.__import__ is guarded_import:
        builtins.__import__ = _original_import


activate_import_firewall = install_import_firewall
ACTIVATE_IMPORT_FIREWALL = install_import_firewall
DEACTIVATE_IMPORT_FIREWALL = deactivate_import_firewall


@contextmanager
def integration_import_allowed():
    t = _token.set(True)
    try:
        yield
    finally:
        _token.reset(t)


@contextmanager
def allow_internal_import():
    """Backward-compatible runtime-internal import permission context."""
    with integration_import_allowed():
        yield


ALLOW_INTERNAL_IMPORT = allow_internal_import


def import_with_integration_permission(name: str) -> ModuleType:
    with integration_import_allowed():
        return importlib.import_module(name)


def assert_import_firewall_installed() -> None:
    if not _env_enabled():
        return
    if builtins.__import__ is not guarded_import:
        raise RuntimeError("Runtime import firewall is not installed")


__all__ = [
    "ACTIVATE_IMPORT_FIREWALL",
    "ALLOW_INTERNAL_IMPORT",
    "DEACTIVATE_IMPORT_FIREWALL",
    "FORBIDDEN_MODULE_PREFIXES",
    "FORBIDDEN_PREFIXES",
    "activate_import_firewall",
    "allow_internal_import",
    "assert_import_firewall_installed",
    "deactivate_import_firewall",
    "guarded_import",
    "import_with_integration_permission",
    "install_import_firewall",
    "integration_import_allowed",
]
