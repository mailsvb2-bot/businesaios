from dataclasses import dataclass


@dataclass(frozen=True)
class ActionStatus:
    value: str
