from __future__ import annotations

"""Final-owner bootstrap composition surface.

This module is the target bootstrap owner for the repository. During migration
it delegates to the existing sovereign runtime bootstrap, while providing a
stable academic destination for future physical moves.
"""

from typing import Any

CANON_BOOTSTRAP_COMPOSE_OWNER = True
CANON_BOOTSTRAP_FINAL_OWNER = True
CANON_BOOTSTRAP_COMPOSE_THIN_DURING_MIGRATION = True
CANON_BOOTSTRAP_COMPOSE_BUILT_RUNTIME_EXPORT = True


def bootstrap(*, acquire_singleton_lock: bool = True) -> None:
    from runtime.bootstrap import bootstrap as runtime_bootstrap

    runtime_bootstrap(acquire_singleton_lock=acquire_singleton_lock)


def bootstrap_runtime(*, project_root: str | None = None) -> Any:
    from runtime.bootstrap import bootstrap_runtime as runtime_bootstrap_runtime

    return runtime_bootstrap_runtime(project_root=project_root)


def get_bootstrapped_runtime() -> Any:
    from runtime.bootstrap import get_bootstrapped_runtime as runtime_get_bootstrapped_runtime

    return runtime_get_bootstrapped_runtime()


def build_runtime(*, project_root: str | None = None) -> Any:
    return bootstrap_runtime(project_root=project_root).artifacts.built_runtime
