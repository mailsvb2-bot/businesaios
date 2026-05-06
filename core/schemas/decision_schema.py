from __future__ import annotations

from typing import Dict, Any
from .base import Schema


class DecisionEnvelopeV1(Schema):

    def validate(self, payload: Dict[str, Any]) -> None:
        if "decision_id" not in payload:
            raise ValueError("decision_id missing")

        if "actions" not in payload:
            raise ValueError("actions missing")

    def normalize(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return payload
