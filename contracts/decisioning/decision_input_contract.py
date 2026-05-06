from __future__ import annotations

from dataclasses import dataclass

from contracts.decisioning.decision_envelope_contract import DecisionEnvelopeContract


@dataclass(frozen=True)
class DecisionInputContract:
    envelope: DecisionEnvelopeContract

    def as_dict(self) -> dict[str, object]:
        return {
            "envelope": self.envelope.as_dict(),
        }
