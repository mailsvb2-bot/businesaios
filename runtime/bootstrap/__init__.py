from __future__ import annotations

"""Legacy package-form runtime bootstrap surface.

This package path is preserved for compatibility and to host thin re-export
submodules, but the actual process/bootstrap owners live in
``runtime.bootstrap``.

Important compatibility note:
Some tests and older callers monkeypatch the historical bootstrap guard
functions and bootstrap state directly on ``runtime.bootstrap``.  To preserve
that behavior without turning this module into a second assembly brain, this
package keeps a very small process-only wrapper that mirrors the original
public surface while delegating full runtime assembly to
``runtime.bootstrap.sovereign_bootstrap``.
"""

import atexit
from importlib import import_module
from typing import Any

from bootstrap.logging_setup import setup_logging
from runtime.bootstrap_process import apply_process_hygiene, maybe_disable_singleton_lock_in_dev_test
from runtime.bootstrap_prod_guards import (
    enforce_production_strict_mode,
    enforce_two_admins_in_prod_or_explain,
    verify_release_attestation_if_needed,
)
from runtime.firewall.import_guard import activate_import_firewall
from runtime.firewall.singleton_lock import SingletonLock

CANON_RUNTIME_PROCESS_BOOTSTRAP = True
CANON_RUNTIME_BOOTSTRAP_PROCESS_ONLY = True
CANON_SOVEREIGN_BOOTSTRAP_PUBLIC_SURFACE = True
CANON_RUNTIME_BOOTSTRAP_PACKAGE_THIN_SHIM = True
CANON_RUNTIME_BOOTSTRAP_DIRECT_PROCESS_OWNER_DELEGATION = True
CANON_RUNTIME_BOOTSTRAP_PACKAGE_LAZY_EXPORTS = True

# Historical public state kept for compatibility with tests and existing code.
_BOOTSTRAP_DONE = False
_SINGLETON_LOCK: SingletonLock | None = None

_EXPORT_MAP: dict[str, tuple[str, str]] = {
    "build_crm_service": ("runtime.bootstrap.crm_bootstrap", "build_crm_service"),
    "build_crm_connector_registry": (
        "runtime.bootstrap.crm_connector_boot",
        "build_crm_connector_registry",
    ),
    "build_crm_provider_registry": (
        "runtime.bootstrap.crm_registry_boot",
        "build_crm_provider_registry",
    ),
    "bootstrap_runtime": ("runtime.bootstrap.sovereign_bootstrap", "bootstrap_runtime"),
    "get_bootstrapped_runtime": (
        "runtime.bootstrap.sovereign_bootstrap",
        "get_bootstrapped_runtime",
    ),
    "BuiltRuntime": ("runtime.bootstrap.runtime_builder", "BuiltRuntime"),
}


def _run_process_bootstrap_compat(*, acquire_singleton_lock: bool = True) -> None:
    global _BOOTSTRAP_DONE

    verify_release_attestation_if_needed()
    enforce_production_strict_mode()
    enforce_two_admins_in_prod_or_explain()
    maybe_disable_singleton_lock_in_dev_test()

    if not _BOOTSTRAP_DONE:
        apply_process_hygiene()
        setup_logging()
        activate_import_firewall()
        _BOOTSTRAP_DONE = True

    _acquire_singleton_lock_if_needed(acquire_singleton_lock=acquire_singleton_lock)


def _load_process_bootstrap_owner():
    return _run_process_bootstrap_compat


def _load_attr(module_name: str, attr_name: str) -> Any:
    return getattr(import_module(module_name), attr_name)


def _release_singleton_lock() -> None:
    global _SINGLETON_LOCK

    lock = _SINGLETON_LOCK
    _SINGLETON_LOCK = None
    if lock is None:
        return
    try:
        lock.release()
    except Exception:
        return


# Compatibility wrapper: guard functions remain monkeypatchable on
# ``runtime.bootstrap`` itself, while the logic stays process-only.
def _acquire_singleton_lock_if_needed(*, acquire_singleton_lock: bool) -> None:
    global _SINGLETON_LOCK

    if not acquire_singleton_lock:
        return
    if _SINGLETON_LOCK is not None:
        return
    lock = SingletonLock()
    lock.acquire()
    _SINGLETON_LOCK = lock
    atexit.register(_release_singleton_lock)


def bootstrap(*, acquire_singleton_lock: bool = True) -> None:
    run_process_bootstrap = _load_process_bootstrap_owner()
    run_process_bootstrap(acquire_singleton_lock=acquire_singleton_lock)


def __getattr__(name: str) -> Any:
    if name in {
        "CANON_RUNTIME_BOOTSTRAP_PROCESS_ONLY",
        "CANON_RUNTIME_PROCESS_BOOTSTRAP",
        "CANON_SOVEREIGN_BOOTSTRAP_PUBLIC_SURFACE",
        "CANON_RUNTIME_BOOTSTRAP_PACKAGE_THIN_SHIM",
        "CANON_RUNTIME_BOOTSTRAP_DIRECT_PROCESS_OWNER_DELEGATION",
        "CANON_RUNTIME_BOOTSTRAP_PACKAGE_LAZY_EXPORTS",
        "_BOOTSTRAP_DONE",
        "_SINGLETON_LOCK",
    }:
        return globals()[name]
    target = _EXPORT_MAP.get(name)
    if target is None:
        raise AttributeError(name)
    module_name, attr_name = target
    value = _load_attr(module_name, attr_name)
    if name not in {"bootstrap_runtime", "get_bootstrapped_runtime"}:
        globals()[name] = value
    return value


__all__ = [
    "CANON_RUNTIME_BOOTSTRAP_DIRECT_PROCESS_OWNER_DELEGATION",
    "CANON_RUNTIME_BOOTSTRAP_PACKAGE_LAZY_EXPORTS",
    "CANON_RUNTIME_BOOTSTRAP_PACKAGE_THIN_SHIM",
    "CANON_RUNTIME_BOOTSTRAP_PROCESS_ONLY",
    "CANON_RUNTIME_PROCESS_BOOTSTRAP",
    "CANON_SOVEREIGN_BOOTSTRAP_PUBLIC_SURFACE",
    "_BOOTSTRAP_DONE",
    "_SINGLETON_LOCK",
    "_release_singleton_lock",
    "apply_process_hygiene",
    "activate_import_firewall",
    "bootstrap",
    "enforce_production_strict_mode",
    "enforce_two_admins_in_prod_or_explain",
    "maybe_disable_singleton_lock_in_dev_test",
    "setup_logging",
    "verify_release_attestation_if_needed",
    "SingletonLock",
    *tuple(_EXPORT_MAP.keys()),
]
