"""Canonical callable-signature helpers.

Used by boot/runtime/core adapter layers that need compatibility without
masking internal provider errors as signature mismatches.
"""

from __future__ import annotations

from inspect import Parameter, signature
from typing import Any
from collections.abc import Callable
from collections.abc import Iterable

CANON_CALL_SIGNATURE_HELPERS = True

def parameters(fn: Callable[..., Any]) -> tuple[Parameter, ...]:
    try:
        return tuple(signature(fn).parameters.values())
    except (TypeError, ValueError):
        return ()


def accepts_keyword(fn: Callable[..., Any], keyword: str) -> bool:
    for param in parameters(fn):
        if param.kind is Parameter.VAR_KEYWORD:
            return True
        if param.name == keyword and param.kind in (
            Parameter.POSITIONAL_OR_KEYWORD,
            Parameter.KEYWORD_ONLY,
        ):
            return True
    return False


def accepts_keywords(fn: Callable[..., Any], keywords: Iterable[str]) -> bool:
    return all(accepts_keyword(fn, keyword) for keyword in keywords)


def accepted_kwargs(fn: Callable[..., Any], kwargs: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in kwargs.items() if accepts_keyword(fn, key)}


def supports_zero_arg_call(fn: Callable[..., Any]) -> bool:
    params = parameters(fn)
    if not params:
        return True
    for param in params:
        if param.kind in (Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD):
            return True
        if param.default is Parameter.empty and param.kind in (
            Parameter.POSITIONAL_ONLY,
            Parameter.POSITIONAL_OR_KEYWORD,
            Parameter.KEYWORD_ONLY,
        ):
            return False
    return True


__all__ = [
    'CANON_CALL_SIGNATURE_HELPERS',
    'accepted_kwargs',
    'accepts_keyword',
    'accepts_keywords',
    'parameters',
    'supports_zero_arg_call',
]
