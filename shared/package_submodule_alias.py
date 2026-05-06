from __future__ import annotations

import sys
from types import ModuleType


CANON_PACKAGE_SUBMODULE_ALIAS = True


def install_package_submodule_alias(module_name: str, submodule_name: str, *, expose_attribute: bool = True) -> None:
    """Expose the package itself as a stable nested submodule alias.

    This keeps historical imports like ``package.catalog`` working after a
    thin surface has been collapsed into the owning package.
    """
    if not module_name or not submodule_name:
        raise ValueError("module_name and submodule_name must be non-empty")
    package = sys.modules.get(module_name)
    if package is None or not isinstance(package, ModuleType):
        raise ModuleNotFoundError(module_name)
    alias_name = f"{module_name}.{submodule_name}"
    existing = sys.modules.get(alias_name)
    if existing is not None and existing is not package:
        raise RuntimeError(
            f"refusing to replace foreign submodule alias {alias_name!r} owned by {getattr(existing, '__name__', type(existing).__name__)}"
        )
    sys.modules[alias_name] = package
    if expose_attribute:
        existing_attr = getattr(package, submodule_name, None)
        if existing_attr is not None and existing_attr is not package:
            raise RuntimeError(
                f"refusing to replace foreign package attribute {module_name}.{submodule_name}"
            )
        setattr(package, submodule_name, package)


__all__ = ["CANON_PACKAGE_SUBMODULE_ALIAS", "install_package_submodule_alias"]
