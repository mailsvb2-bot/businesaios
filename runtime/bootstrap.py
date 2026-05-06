from __future__ import annotations

"""Explicit process-hygiene bootstrap for runtime execution.

This module owns only process guards and singleton/runtime firewalls. It must
not become an alternative app assembly path.

Compatibility note:
- this file remains the public ``runtime.bootstrap`` module;
- it also exposes a package-like submodule namespace via ``__path__`` so the
  sovereign bootstrap implementation can live in dedicated submodules without
  breaking legacy imports.
"""

from pathlib import Path
from typing import Any

# Make this module behave like a package so ``runtime.bootstrap.<submodule>``
# can resolve to files stored under runtime/bootstrap/.
__path__ = [str(Path(__file__).with_name("bootstrap"))]

CANON_RUNTIME_PROCESS_BOOTSTRAP = True
CANON_RUNTIME_BOOTSTRAP_PROCESS_ONLY = True
CANON_SOVEREIGN_BOOTSTRAP_PUBLIC_SURFACE = True
CANON_RUNTIME_BOOTSTRAP_DIRECT_PROCESS_OWNER_DELEGATION = True


def _load_process_bootstrap_owner() -> Any:
    from runtime.bootstrap.process_bootstrap import run_process_bootstrap

    return run_process_bootstrap


def _load_sovereign_bootstrap() -> Any:
    from runtime.bootstrap.sovereign_bootstrap import (
        bootstrap_runtime as _bootstrap_runtime,
        get_bootstrapped_runtime as _get_runtime,
    )

    return _bootstrap_runtime, _get_runtime


def bootstrap(*, acquire_singleton_lock: bool = True) -> None:
    """Run process hygiene and optionally own the singleton lock.

    This is the historical runtime bootstrap surface and remains intentionally
    small. The canonical full runtime assembly path lives in
    ``runtime.bootstrap.sovereign_bootstrap.bootstrap_runtime``.
    """
    run_process_bootstrap = _load_process_bootstrap_owner()
    run_process_bootstrap(acquire_singleton_lock=acquire_singleton_lock)



def bootstrap_runtime(*, project_root: str | None = None):
    bootstrap_runtime_owner, _ = _load_sovereign_bootstrap()
    return bootstrap_runtime_owner(project_root=project_root)



def get_bootstrapped_runtime():
    _, get_runtime = _load_sovereign_bootstrap()
    return get_runtime()


__all__ = [
    "CANON_RUNTIME_BOOTSTRAP_DIRECT_PROCESS_OWNER_DELEGATION",
    "CANON_RUNTIME_BOOTSTRAP_PROCESS_ONLY",
    "CANON_RUNTIME_PROCESS_BOOTSTRAP",
    "CANON_SOVEREIGN_BOOTSTRAP_PUBLIC_SURFACE",
    "bootstrap",
    "bootstrap_runtime",
    "get_bootstrapped_runtime",
]
