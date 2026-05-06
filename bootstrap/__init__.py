from __future__ import annotations

"""Bootstrap package root.

This package is the final owner for assembly-facing bootstrap surfaces.
Keep package import side effects minimal to avoid circular imports during
observability/config initialization.
"""

CANON_BOOTSTRAP_PACKAGE_ROOT = True
CANON_BOOTSTRAP_PACKAGE_FINAL_OWNER = True
CANON_BOOTSTRAP_PACKAGE_LAZY_EXPORTS = True


def boot_application(*args, **kwargs):
    from bootstrap.app_boot import boot_application as _boot_application

    return _boot_application(*args, **kwargs)


def bootstrap(*args, **kwargs):
    from bootstrap.compose import bootstrap as _bootstrap

    return _bootstrap(*args, **kwargs)


def bootstrap_runtime(*args, **kwargs):
    from bootstrap.compose import bootstrap_runtime as _bootstrap_runtime

    return _bootstrap_runtime(*args, **kwargs)


def build_runtime(*args, **kwargs):
    from bootstrap.compose import build_runtime as _build_runtime

    return _build_runtime(*args, **kwargs)


def get_bootstrapped_runtime():
    from bootstrap.compose import get_bootstrapped_runtime as _get_bootstrapped_runtime

    return _get_bootstrapped_runtime()


__all__ = [
    "CANON_BOOTSTRAP_PACKAGE_ROOT",
    "CANON_BOOTSTRAP_PACKAGE_FINAL_OWNER",
    "CANON_BOOTSTRAP_PACKAGE_LAZY_EXPORTS",
    "boot_application",
    "bootstrap",
    "bootstrap_runtime",
    "build_runtime",
    "get_bootstrapped_runtime",
]
