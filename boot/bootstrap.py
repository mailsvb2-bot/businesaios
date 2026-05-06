from __future__ import annotations

"""Compatibility shell for the final bootstrap owner."""

from importlib import import_module

CANON_APP_BOOTSTRAP = True
CANON_LEGACY_BOOTSTRAP_SHIM = True
CANON_BOOTSTRAP_THIN_SHIM = True
CANON_BOOTSTRAP_DELEGATES_TO_BOOTSTRAP_COMPOSE = True
CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API = "bootstrap.compose"


def _load_attr(module_name: str, attr_name: str):
    return getattr(import_module(module_name), attr_name)


def bootstrap(*, acquire_singleton_lock: bool = True) -> object:
    compose_bootstrap = _load_attr("bootstrap.compose", "bootstrap")
    compose_bootstrap(acquire_singleton_lock=acquire_singleton_lock)
    get_runtime = _load_attr("bootstrap.compose", "get_bootstrapped_runtime")
    return get_runtime()


def build_runtime(*, project_root: str | None = None):
    compose_build_runtime = _load_attr("bootstrap.compose", "build_runtime")
    return compose_build_runtime(project_root=project_root)


__all__ = [
    "CANON_APP_BOOTSTRAP",
    "CANON_LEGACY_BOOTSTRAP_SHIM",
    "CANON_BOOTSTRAP_THIN_SHIM",
    "CANON_BOOTSTRAP_DELEGATES_TO_BOOTSTRAP_COMPOSE",
    "CANONICAL_OWNER_BOOTSTRAP_PUBLIC_API",
    "bootstrap",
    "build_runtime",
]
