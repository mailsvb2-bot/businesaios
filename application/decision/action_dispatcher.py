from __future__ import annotations

from dataclasses import dataclass

from application.decision.ports import DecisionExecutionPortProtocol

CANON_APPLICATION_DISPATCHER_ENVELOPE_ONLY = True


class DecisionEnvelopeRequiredError(TypeError):
    pass


@dataclass(frozen=True)
class ActionDispatcher:
    """Execution-only adapter for an already-issued DecisionEnvelope.

    It cannot select, decide, sign, or transform a recommendation into an action.
    The supplied port must expose the canonical ``execute(envelope)`` contract,
    compatible with ``RuntimeExecutor.execute``.
    """

    decision_execution_port: DecisionExecutionPortProtocol

    def dispatch(self, envelope: object):
        decision = getattr(envelope, "decision", None)
        if decision is None:
            raise DecisionEnvelopeRequiredError(
                "canonical DecisionEnvelope required"
            )
        if not str(
            getattr(decision, "decision_id", "") or ""
        ).strip():
            raise DecisionEnvelopeRequiredError(
                "DecisionEnvelope decision_id required"
            )
        execute = getattr(self.decision_execution_port, "execute", None)
        if not callable(execute):
            raise TypeError(
                "decision execution port requires execute(envelope)"
            )
        return execute(envelope)


__all__ = [
    "ActionDispatcher",
    "CANON_APPLICATION_DISPATCHER_ENVELOPE_ONLY",
    "DecisionEnvelopeRequiredError",
]
