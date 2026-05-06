from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from execution.inference_provider_contract import InferenceResponse
from execution.inference_result_verifier import InferenceVerificationOutcome


CANON_INFERENCE_EXECUTION_RESULT_CONTRACT = True


@dataclass(frozen=True)
class InferenceExecutionRecord:
    response: InferenceResponse
    verification: InferenceVerificationOutcome
    selected_provider: str
    selected_tier: str
    evidence: Mapping[str, str] = field(default_factory=dict)
