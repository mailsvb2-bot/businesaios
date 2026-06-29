"""Canonical runtime package alias namespace for runtime.pricing public API."""

from __future__ import annotations


from runtime.package_alias_namespace import build_package_alias_namespace

CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE = True

_PUBLIC_ATTRS = {
    "PricingRouteViolation": ("core.pricing.rl.guard", "PricingRouteViolation"),
    "PricingSelectionContext": ("core.pricing.rl.guard", "PricingSelectionContext"),
}

__getattr__, __dir__, __all__ = build_package_alias_namespace(
    __name__,
    _PUBLIC_ATTRS,
    extra_exports=['CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE'],
    )

