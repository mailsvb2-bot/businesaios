"""Canonical runtime package alias namespace for runtime.payments public API."""

from __future__ import annotations

from runtime.package_alias_namespace import build_package_alias_namespace

CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE = True
CANON_RUNTIME_PAYMENTS_NAMESPACE = True
CANON_RUNTIME_PAYMENTS_PUBLIC_API = True

_PUBLIC_ATTRS = {
    "CANON_RUNTIME_PAYMENTS_NAMESPACE": ("runtime.payments", "CANON_RUNTIME_PAYMENTS_NAMESPACE"),
    "CANON_RUNTIME_PAYMENTS_PUBLIC_API": ("runtime.payments", "CANON_RUNTIME_PAYMENTS_PUBLIC_API"),
    "parse_yookassa_notification": ("core.payments.yookassa_webhook", "parse_notification"),
    "verify_yookassa_webhook": ("core.payments.yookassa_webhook", "verify_webhook"),
}

__getattr__, __dir__, __all__ = build_package_alias_namespace(
    __name__,
    _PUBLIC_ATTRS,
    extra_exports=['CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE', 'CANON_RUNTIME_PAYMENTS_NAMESPACE', 'CANON_RUNTIME_PAYMENTS_PUBLIC_API'],
    install_public_api=True
)
