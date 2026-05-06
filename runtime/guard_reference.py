from __future__ import annotations

import logging
import threading

from runtime.decision import DecisionEnvelope
from survival.controller import SurvivalVerdict

logger = logging.getLogger("runtime.guard")


def verify_and_lock_reference(*, verifier, ledger, survival, lock: threading.Lock, envelope: DecisionEnvelope) -> SurvivalVerdict:
    """Reference-mode execution law.

    Order is fixed by Canon:
      1. verify signature
      2. check idempotency
      3. ask survival controller
    """
    if not verifier.verify(envelope):
        raise RuntimeError("invalid_decision_signature")

    with lock:
        if ledger.already_executed(envelope.decision_id):
            raise RuntimeError("decision_already_executed")

    verdict = survival.evaluate()
    if not verdict.allow_execution:
        raise RuntimeError(f"execution_blocked:{verdict.reason}")
    return verdict


def commit_reference_execution(*, ledger, lock: threading.Lock, envelope: DecisionEnvelope) -> None:
    with lock:
        ledger.mark_executed(envelope.decision_id)

    logger.info(
        "decision_committed",
        extra={"decision_id": envelope.decision_id, "action": envelope.action},
    )
