from __future__ import annotations

"""Decision archive contract and test-safe in-memory implementation."""

from dataclasses import dataclass
from typing import Protocol

from core.ai.decision import DecisionEnvelope


class DecisionArchive(Protocol):
    def put(self, env: DecisionEnvelope) -> None: ...
    def get(self, decision_id: str) -> DecisionEnvelope | None: ...


@dataclass
class MemoryDecisionArchive:
    _store: dict[str, DecisionEnvelope]

    def __init__(self):
        self._store = {}

    def put(self, env: DecisionEnvelope) -> None:
        self._store[str(env.decision.decision_id)] = env

    def get(self, decision_id: str) -> DecisionEnvelope | None:
        return self._store.get(str(decision_id))
