from __future__ import annotations

"""Compatibility import surface for execute-action API stack.

Canonical implementation owner: adapters.api.fastapi.control_plane_routes and
runtime.application._ports_impl. This file stays adapter-only.
"""

CANON_EXECUTE_ACTION_STACK_BUNDLE_THIN_ADAPTER = True

__all__: list[str] = [
    "CANON_EXECUTE_ACTION_STACK_BUNDLE_THIN_ADAPTER",
]
