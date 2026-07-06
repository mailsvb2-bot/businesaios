from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ..contracts import OutcomeReader as OutcomeReaderContract
from ..types import OutcomeFact


@dataclass(frozen=True)
class OutcomeReader(OutcomeReaderContract):
    outcomes_by_entity: Mapping[str, Sequence[OutcomeFact]]

    def list_outcomes(self, entity_id: str) -> Sequence[OutcomeFact]:
        return tuple(self.outcomes_by_entity.get(entity_id, ()))
