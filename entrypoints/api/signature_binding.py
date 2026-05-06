from __future__ import annotations

import inspect
from typing import Any, Callable, Mapping


CANON_API_SIGNATURE_BINDING = True


def supported_kwargs(fn: Callable[..., Any], /, **candidates: Any) -> dict[str, Any]:
    parameters = inspect.signature(fn).parameters
    accepts_var_kw = any(param.kind is inspect.Parameter.VAR_KEYWORD for param in parameters.values())
    if accepts_var_kw:
        return dict(candidates)
    return {key: value for key, value in candidates.items() if key in parameters}


def supports_keyword(fn: Callable[..., Any], name: str) -> bool:
    parameters = inspect.signature(fn).parameters
    if name in parameters:
        return True
    return any(param.kind is inspect.Parameter.VAR_KEYWORD for param in parameters.values())


__all__ = [
    'CANON_API_SIGNATURE_BINDING',
    'supported_kwargs',
    'supports_keyword',
]
