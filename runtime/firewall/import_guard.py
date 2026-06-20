import builtins
import contextlib
import contextvars
import importlib.abc
import inspect
import sys
from types import FrameType

from runtime.observability.error_handling import swallow

# Modules that are considered "real-world integrations" and must be reachable ONLY via
# runtime.executor -> (private effects impl) (hermetic runtime law).
FORBIDDEN_MODULE_PREFIXES = [
    "runtime._internal",
    "payments",
    "messaging",
    "external_api",
]

# Canonical allowed importer modules (best-effort, used when we can identify a caller).
ALLOWED_CALLERS = {
    "runtime.executor",
    "runtime.effects",
    "runtime.executor_effects",
    "runtime.execution.executor_state",
    "runtime.lazy_namespace",
    "runtime.market_intelligence_provider_support",
}
_CANONICAL_INTERNAL_IMPORT_WINDOW_CALLERS = {
    "runtime.executor",
    "runtime.effects",
    "runtime.executor_effects",
    "runtime.execution.executor_state",
}

# Strong gate: even if caller detection fails (e.g. stripped frames / frozen importlib),
# importing runtime._internal is allowed ONLY within this context.
_ALLOW_INTERNAL_IMPORT: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "ALLOW_INTERNAL_IMPORT", default=False
)

# Public alias (for tests & readability). Do not mutate directly.
ALLOW_INTERNAL_IMPORT = _ALLOW_INTERNAL_IMPORT


def _infer_caller_module_for_allow_internal_import() -> str:
    """Best-effort inference of the first *external* caller module name.

    We skip frames that belong to this module, contextlib, inspect/importlib wrappers.
    """
    skip_prefixes = (
        __name__,
        "contextlib",
        "inspect",
        "importlib",
    )
    for frame_info in inspect.stack()[2:]:
        mod = inspect.getmodule(frame_info.frame)
        if not mod or not getattr(mod, "__name__", None):
            continue
        name = mod.__name__
        if any(name == p or name.startswith(p + ".") for p in skip_prefixes):
            continue
        return name
    return "<unknown>"


@contextlib.contextmanager
def allow_internal_import():
    caller = _infer_caller_module_for_allow_internal_import()
    # Only canonical executor/effects wiring modules may open the internal import window.
    if caller not in _CANONICAL_INTERNAL_IMPORT_WINDOW_CALLERS:
        raise PermissionError(
            f"[FIREWALL] allow_internal_import is restricted to canonical executor wiring (caller={caller})"
        )
    token = _ALLOW_INTERNAL_IMPORT.set(True)
    try:
        yield
    finally:
        _ALLOW_INTERNAL_IMPORT.reset(token)


def _infer_caller_module() -> str:
    # Walk the stack and pick the first "user" frame that is not importlib and not this module.
    # This is more robust than inspect.stack()[2], which can yield "unknown" on some setups.
    try:
        frame: FrameType | None = sys._getframe(1)
    except Exception:
        frame = None

    while frame is not None:
        g = frame.f_globals or {}
        mod = g.get("__name__", "") or ""
        _ = g.get("__file__", "") or ""
        if mod and not mod.startswith(("importlib", "runtime.firewall.import_guard")):
            return mod
        # Skip builtins and C-frames
        frame = frame.f_back
    return "unknown"


_original_import = builtins.__import__


def _is_forbidden(name: str) -> bool:
    return any(name.startswith(p) for p in FORBIDDEN_MODULE_PREFIXES)


def _is_test_caller(caller: str) -> bool:
    if caller == "conftest":
        return True
    if caller.startswith(("_pytest.", "tests.", "test_")):
        return True
    if ".tests." in caller or caller.endswith(".conftest"):
        return True
    leaf = caller.rsplit(".", 1)[-1]
    return leaf.startswith("test_")


def _allow_forbidden(name: str, caller: str) -> bool:
    # Hard allow only for runtime._internal under explicit context.
    if name.startswith("runtime._internal"):
        if _ALLOW_INTERNAL_IMPORT.get():
            return True
        # Internal modules may import each other inside the sealed zone.
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
    fromlist = ()
    if len(args) >= 4:
        fromlist = args[3] or ()
    else:
        fromlist = kwargs.get("fromlist") or ()
    caller = _infer_caller_module()
    if _is_forbidden(name) and not _allow_forbidden(name, caller):
        raise ImportError(f"[FIREWALL] Forbidden integration import: {name} by {caller}")
    try:
        return _original_import(name, *args, **kwargs)
    except ModuleNotFoundError as exc:
        # Do not hide import errors for project-owned modules or optional deps already installed.
        if not name.startswith(("yaml", "pydantic_settings")):
            raise
        swallow(__name__, "optional_dependency_missing", exc)
        raise


# Installation is opt-in in production bootstrap/tests.
def install_import_guard():
    if builtins.__import__ is not guarded_import:
        builtins.__import__ = guarded_import


def activate_import_firewall():
    """Backward-compatible public activation surface for bootstrap.

    The owner remains this module; bootstrap must not duplicate firewall install
    logic or import private internals directly.
    """

    install_import_guard()


def uninstall_import_guard():
    if builtins.__import__ is guarded_import:
        builtins.__import__ = _original_import


__all__ = [
    "ALLOW_INTERNAL_IMPORT",
    "activate_import_firewall",
    "allow_internal_import",
    "guarded_import",
    "install_import_guard",
    "uninstall_import_guard",
]
