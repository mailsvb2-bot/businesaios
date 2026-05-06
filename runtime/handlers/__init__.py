"""Canonical runtime handlers package.

This package is the only canonical import surface for runtime handlers.
The historical ``runtime/handlers.py`` module is removed to avoid a module/package
name collision that previously forced fallback loaders and non-canonical imports.
"""

from .registry import ActionHandlerRegistry

__all__ = ['ActionHandlerRegistry']
