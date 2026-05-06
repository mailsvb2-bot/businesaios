from __future__ import annotations

"""Canonical runtime package alias namespace for runtime.reward public API."""

from runtime.package_alias_namespace import build_package_alias_namespace

CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE = True

_PUBLIC_ATTRS = {
    "RewardObservationContext": ("core.reward.contracts", "RewardObservationContext"),
    "RewardService": ("core.reward.service", "RewardService"),
}

__getattr__, __dir__, __all__ = build_package_alias_namespace(
    __name__,
    _PUBLIC_ATTRS,
    extra_exports=['CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE'],
    )

