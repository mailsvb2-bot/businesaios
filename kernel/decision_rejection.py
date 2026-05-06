from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionRejection:
    reason_code: str
    message: str
