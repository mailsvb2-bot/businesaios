"""Thin boot-wiring adapter for core handler registration."""

from runtime.boot_impl.handler_groups_core import (
    _catalog_action_for_handler,
    _track_marker_event,
    register_core_handlers,
)

__all__ = [
    "_catalog_action_for_handler",
    "_track_marker_event",
    "register_core_handlers",
]
