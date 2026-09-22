"""Canonical runtime package alias namespace for runtime.events public API."""

from __future__ import annotations

from runtime.package_alias_namespace import build_package_alias_namespace

CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE = True
CANON_RUNTIME_EVENTS_PUBLIC_API = True

_PUBLIC_ATTRS = {
    'CANON_RUNTIME_EVENTS_PUBLIC_API': ('runtime.events', 'CANON_RUNTIME_EVENTS_PUBLIC_API'),
    'EventLog': ('core.events.log', 'EventLog'),
    'ACTION_AMBIGUOUS': ('core.events.event_types', 'ACTION_AMBIGUOUS'),
    'ACTION_AUTHORIZED': ('core.events.event_types', 'ACTION_AUTHORIZED'),
    'ACTION_EXECUTED': ('core.events.event_types', 'ACTION_EXECUTED'),
    'ACTION_FAILED': ('core.events.event_types', 'ACTION_FAILED'),
}

__getattr__, __dir__, __all__ = build_package_alias_namespace(
    __name__,
    _PUBLIC_ATTRS,
    extra_exports=['CANON_RUNTIME_PACKAGE_ALIAS_NAMESPACE', 'CANON_RUNTIME_EVENTS_PUBLIC_API'],
    install_public_api=True
)
