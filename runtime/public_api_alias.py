from __future__ import annotations

import sys
from types import ModuleType

CANON_RUNTIME_PUBLIC_API_ALIAS = True
CANON_NO_ALIAS_EXPANSION = True


def install_public_api_alias(module_name: str, *, expose_attribute: bool = True) -> None:
    cleaned = str(module_name or '').strip()
    if not cleaned:
        raise RuntimeError('public api alias collision: empty module name')
    if any(not part.isidentifier() for part in cleaned.split('.')):
        raise RuntimeError(f'public api alias collision: invalid module name: {module_name}')

    package = sys.modules.get(cleaned)
    if not isinstance(package, ModuleType):
        return

    public_api_name = f'{cleaned}.public_api'
    alias_target = sys.modules.get(public_api_name)
    if alias_target is None:
        alias_target = package
        sys.modules[public_api_name] = alias_target
    elif not isinstance(alias_target, ModuleType):
        raise RuntimeError(f'public api alias collision: {public_api_name}')

    nested_alias = f'{public_api_name}.public_api'
    existing_nested = sys.modules.get(nested_alias)
    if existing_nested not in (None, alias_target):
        raise RuntimeError(f'public api alias collision: {nested_alias}')
    sys.modules[nested_alias] = alias_target

    if expose_attribute:
        current = getattr(alias_target, 'public_api', None)
        if current not in (None, alias_target):
            raise RuntimeError(f'public api attribute collision: {nested_alias}')
        setattr(alias_target, 'public_api', alias_target)


__all__ = [
    'CANON_NO_ALIAS_EXPANSION',
    'CANON_RUNTIME_PUBLIC_API_ALIAS',
    'install_public_api_alias',
]
