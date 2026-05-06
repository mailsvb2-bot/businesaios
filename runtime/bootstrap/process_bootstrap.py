from __future__ import annotations

"""Canonical internal process-bootstrap owner.

This module owns only runtime process hygiene, singleton lock discipline, and
related fail-closed guards. It is intentionally separate from sovereign runtime
assembly so internal bootstrap code does not need to route back through the
public ``runtime.bootstrap`` compat surface.
"""

import atexit
from dataclasses import dataclass

from bootstrap.logging_setup import setup_logging
from runtime.bootstrap_process import apply_process_hygiene, maybe_disable_singleton_lock_in_dev_test
from runtime.bootstrap_prod_guards import (
    enforce_production_strict_mode,
    enforce_two_admins_in_prod_or_explain,
    verify_release_attestation_if_needed,
)
from runtime.firewall.import_guard import activate_import_firewall
from runtime.firewall.singleton_lock import SingletonLock

CANON_RUNTIME_PROCESS_BOOTSTRAP_OWNER = True
CANON_RUNTIME_PROCESS_BOOTSTRAP_INTERNAL_ONLY = True
CANON_RUNTIME_PROCESS_BOOTSTRAP_NO_RUNTIME_ASSEMBLY = True


@dataclass
class _ProcessBootstrapState:
    bootstrap_done: bool = False
    singleton_lock: SingletonLock | None = None


_STATE = _ProcessBootstrapState()


def _release_singleton_lock() -> None:
    lock = _STATE.singleton_lock
    _STATE.singleton_lock = None
    if lock is None:
        return
    try:
        lock.release()
    except Exception:
        return


def _enforce_runtime_process_guards() -> None:
    verify_release_attestation_if_needed()
    enforce_production_strict_mode()
    enforce_two_admins_in_prod_or_explain()
    maybe_disable_singleton_lock_in_dev_test()


def _acquire_singleton_lock_if_needed(*, acquire_singleton_lock: bool) -> None:
    if not acquire_singleton_lock:
        return
    if _STATE.singleton_lock is not None:
        return
    lock = SingletonLock()
    lock.acquire()
    _STATE.singleton_lock = lock
    atexit.register(_release_singleton_lock)


def run_process_bootstrap(*, acquire_singleton_lock: bool = True) -> None:
    """Run process guards and own the singleton lock when needed.

    This must stay process-only. It must not build runtime objects, choose
    alternate assembly paths, or become a second bootstrap brain.
    """
    _enforce_runtime_process_guards()
    if _STATE.bootstrap_done:
        _acquire_singleton_lock_if_needed(acquire_singleton_lock=acquire_singleton_lock)
        return

    apply_process_hygiene()
    setup_logging()
    activate_import_firewall()
    _acquire_singleton_lock_if_needed(acquire_singleton_lock=acquire_singleton_lock)
    _STATE.bootstrap_done = True


__all__ = [
    "CANON_RUNTIME_PROCESS_BOOTSTRAP_INTERNAL_ONLY",
    "CANON_RUNTIME_PROCESS_BOOTSTRAP_NO_RUNTIME_ASSEMBLY",
    "CANON_RUNTIME_PROCESS_BOOTSTRAP_OWNER",
    "run_process_bootstrap",
]
