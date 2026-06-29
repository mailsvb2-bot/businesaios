"""Security primitives for sandboxed execution.

The historical ``runtime.security.public_api`` import path is preserved as a
package alias to avoid a second one-symbol shim file.
"""

from __future__ import annotations


from runtime.package_alias_namespace import build_package_alias_namespace

CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE = True

_PUBLIC_ATTRS = {
    "verify_manifest": ("core.security.release_manifest", "verify_manifest"),
}

__getattr__, __dir__, __all__ = build_package_alias_namespace(
    __name__,
    _PUBLIC_ATTRS,
    extra_exports=['CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE'],
    )

