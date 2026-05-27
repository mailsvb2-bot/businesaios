import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class EffectCapability:
    token: str

def issue_capability() -> EffectCapability:
    return EffectCapability(token=secrets.token_hex(32))
