from __future__ import annotations

"""Canonical runtime contract for world-state access.

Runtime code may construct and type world state values through this surface
without binding itself to core AI internals directly.
"""

RUNTIME_WORLD_STATE_PUBLIC_API = True
WORLD_STATE_CANON = "runtime.world_state"
CANONICAL_WORLD_STATE_IMPORT_PATH = "kernel.world_state.WorldStateV1"

__all__ = [
    "CANONICAL_WORLD_STATE_IMPORT_PATH",
    "RUNTIME_WORLD_STATE_PUBLIC_API",
    "WORLD_STATE_CANON",
]
