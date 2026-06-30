"""Canonical runtime package alias namespace for runtime.ledger public API."""

from __future__ import annotations


from runtime.package_alias_namespace import build_package_alias_namespace

CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE = True

_PUBLIC_ATTRS = {
    "GENESIS": ("core.utils.hash_chain", "GENESIS"),
    "entry_hash": ("core.utils.hash_chain", "entry_hash"),
    "payload_hash": ("core.utils.canonical", "payload_hash"),
}

__getattr__, __dir__, __all__ = build_package_alias_namespace(
    __name__,
    _PUBLIC_ATTRS,
    extra_exports=['CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE'],
    )

