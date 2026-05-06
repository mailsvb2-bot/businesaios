from __future__ import annotations

"""Behavior-graph storage package.

The canonical SQLite owner is ``sqlite_behavior_graph_store``. Historical split
modules are served via compat aliases so old imports stay stable without
keeping a second implementation tree.
"""

import importlib
from typing import Any

from runtime.lazy_namespace import install_module_aliases

CANON_BEHAVIOR_GRAPH_NAMESPACE = True

_ALIAS_MAP = {
    "sqlite_behavior_graph_store_part1": "runtime.platform.behavior_graph.sqlite_behavior_graph_store",
    "sqlite_behavior_graph_store_part2": "runtime.platform.behavior_graph.sqlite_behavior_graph_store",
}

install_module_aliases(__name__, _ALIAS_MAP)


def __getattr__(name: str) -> Any:
    if name == "SqliteBehaviorGraphStore":
        return importlib.import_module("runtime.platform.behavior_graph.sqlite_behavior_graph_store").SqliteBehaviorGraphStore
    if name == "PostgresBehaviorGraphStore":
        return importlib.import_module("runtime.platform.behavior_graph.postgres_behavior_graph_store").PostgresBehaviorGraphStore
    raise AttributeError(name)
