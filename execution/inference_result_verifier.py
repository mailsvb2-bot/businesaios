from __future__ import annotations

from dataclasses import dataclass

from execution.inference_provider_contract import InferenceResponse


CANON_INFERENCE_RESULT_VERIFIER = True


@dataclass(frozen=True)
class InferenceVerificationOutcome:
    accepted: bool
    reason: str
    anomalies: tuple[str, ...] = ()


class InferenceResultVerifier:
    def verify(self, response: InferenceResponse) -> InferenceVerificationOutcome:
        anomalies: list[str] = []
        if not str(response.output_text).strip():
            anomalies.append('empty_output')
        if int(response.completion_tokens) <= 0:
            anomalies.append('non_positive_completion_tokens')
        accepted = not anomalies
        return InferenceVerificationOutcome(
            accepted=accepted,
            reason='accepted' if accepted else f"rejected:{','.join(anomalies)}",
            anomalies=tuple(anomalies),
        )
