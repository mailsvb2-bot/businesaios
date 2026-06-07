from __future__ import annotations

from collections.abc import Mapping

from shared.alias_modules import register_alias_modules as _register_alias_modules


def register_alias_modules(*, package_name: str, source_module: str, aliases: Mapping[str, str]) -> None:
    """Compatibility wrapper around the shared alias-module installer."""
    _register_alias_modules(package_name=package_name, source_module=source_module, aliases=aliases)
