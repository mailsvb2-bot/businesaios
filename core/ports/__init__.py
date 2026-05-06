"""Ports (hexagonal boundaries).

Core depends on ports, platform_layer provides adapters.
"""

from core.ports.behavior_graph_store import BehaviorGraphStore

__all__ = [
    "BehaviorGraphStore",
]
