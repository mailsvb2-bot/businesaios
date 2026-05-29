from __future__ import annotations

from typing import Any, Dict

from .base import Schema


class DecisionEnvelopeV1(Schema):

    def validate(self, payload: dict[str, Any]) -> None:
        if "decision_id" not in payload:
            raise ValueError("decision_id missing")

        if "actions" not in payload:
            raise ValueError("actions missing")

    def normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload
