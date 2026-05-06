from __future__ import annotations

"""Canonical runtime package alias namespace for runtime.recovery_support public API."""

from runtime.package_alias_namespace import build_package_alias_namespace

CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE = True

_PUBLIC_ATTRS = {
    "DecisionArchive": ("core.ai.decision_archive", "DecisionArchive"),
    "log_exception_throttled": ("core.observability.errors", "log_exception_throttled"),
}

__getattr__, __dir__, __all__ = build_package_alias_namespace(
    __name__,
    _PUBLIC_ATTRS,
    extra_exports=['CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE'],
    )

