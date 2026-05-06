from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


DECISION_GRAPH_CONTRACT_VERSION = "DGC-CONTRACT-V1"


@dataclass(frozen=True)
class DecisionGraphEdge:
    src: str
    dst: str
    kind: str


@dataclass(frozen=True)
class DecisionGraph:
    nodes: Tuple[str, ...]
    edges: Tuple[DecisionGraphEdge, ...]
