from __future__ import annotations

from core.ai.decision_contracts import Decision as Decision
from core.ai.decision_contracts import DecisionEnvelope


def _contains_secret_keys(obj) -> bool:
    SUSPECT = ["SECRET", "TOKEN", "KEY", "PASSWORD"]
    if isinstance(obj, dict):
        for k, v in obj.items():
            if any(s in str(k).upper() for s in SUSPECT):
                return True
            if _contains_secret_keys(v):
                return True
    elif isinstance(obj, list | tuple):
        return any(_contains_secret_keys(x) for x in obj)
    return False


def _decision_envelope_verify(self) -> None:
    from kernel.decision_crypto import assert_envelope_signature_surface

    assert_envelope_signature_surface(self)
    if _contains_secret_keys(self.decision.payload):
        raise RuntimeError("Secret leak into Decision Ring payload")
    if self.decision.expires_at_ms < self.decision.issued_at_ms:
        raise RuntimeError("Invalid timestamps")


# Bind as method without changing dataclass definition shape
DecisionEnvelope.verify = _decision_envelope_verify  # type: ignore[attr-defined]
