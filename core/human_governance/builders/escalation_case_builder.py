from __future__ import annotations

from ..contracts import EscalationReader


class EscalationCaseBuilder:
    def __init__(self, escalation_reader: EscalationReader) -> None:
        self._escalation_reader = escalation_reader

    def build(self, review_id: str) -> dict[str, object]:
        open_escalations = self._escalation_reader.read_open_escalations(limit=1000)
        matches = [item for item in open_escalations if item.review_id == review_id]

        return {
            "review_id": review_id,
            "open_escalations": matches,
            "has_open_escalation": bool(matches),
        }
