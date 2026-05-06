from dataclasses import dataclass


@dataclass(frozen=True)
class DecisionReason:
    code: str
    message: str
