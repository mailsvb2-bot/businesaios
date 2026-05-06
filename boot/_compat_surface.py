from __future__ import annotations

"""Shared helpers for boot transition alias surfaces.

These helpers keep the historical import ABI alive while avoiding duplicated
import-time alias installation logic across ``boot.factories`` and
``boot.registrations``. They do not introduce new runtime owners; they only
provide thin transition plumbing on top of canonical modules.
"""

from importlib import import_module
from typing import Mapping

from shared.alias_modules import install_alias_modules


def validate_compat_exports(*, module_label: str, exports: Mapping[str, str]) -> None:
    seen_modules: set[str] = set()
    for export_name, module_name in dict(exports).items():
        normalized_export = str(export_name).strip()
        normalized_module = str(module_name).strip()
        if not normalized_export:
            raise ValueError(f"{module_label} export name must not be blank")
        if not normalized_module:
            raise ValueError(
                f"{module_label} module alias for export '{normalized_export}' must not be blank"
            )
        if normalized_module in seen_modules:
            raise ValueError(
                f"{module_label} compatibility alias '{normalized_module}' is declared more than once"
            )
        seen_modules.add(normalized_module)


def install_boot_compat_aliases(
    *,
    package_name: str,
    owner_module: str,
    exports: Mapping[str, str],
    module_label: str,
) -> None:
    validate_compat_exports(module_label=module_label, exports=exports)
    owner = import_module(owner_module)
    missing_exports = [name for name in dict(exports) if not hasattr(owner, name)]
    if missing_exports:
        raise AttributeError(
            f"{module_label} owner module '{owner_module}' is missing exports: " + ", ".join(sorted(missing_exports))
        )
    install_alias_modules(
        package_name=package_name,
        module_exports={
            module_name: {export_name: f"{owner_module}:{export_name}"}
            for export_name, module_name in dict(exports).items()
        },
    )


__all__ = [
    "install_boot_compat_aliases",
    "validate_compat_exports",
]
