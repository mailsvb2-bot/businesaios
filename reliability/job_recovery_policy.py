from __future__ import annotations

from dataclasses import dataclass


CANON_JOB_RECOVERY_POLICY = True


@dataclass(frozen=True)
class JobRecoveryDecision:
    action: str
    reason: str


@dataclass(frozen=True)
class JobRecoveryPolicy:
    restart_from_scratch_stages: tuple[str, ...] = ("request", "world_state")
    resume_from_stage_stages: tuple[str, ...] = (
        "decision",
        "executable_action",
        "execution",
        "verification",
        "state_update",
        "evidence",
    )
    terminal_stages: tuple[str, ...] = ("completed", "failed")

    def classify(
        self,
        *,
        latest_stage: str | None,
        outbox_claimable: bool,
        idempotency_in_progress: bool,
        anomalies_present: bool,
    ) -> JobRecoveryDecision:
        if anomalies_present:
            return JobRecoveryDecision(action="quarantine", reason="reconciliation_anomaly")
        if latest_stage is None:
            return JobRecoveryDecision(action="restart", reason="no_checkpoint")
        if latest_stage in self.restart_from_scratch_stages:
            return JobRecoveryDecision(action="restart", reason=f"restart_from_{latest_stage}")
        if latest_stage in self.resume_from_stage_stages:
            if outbox_claimable:
                return JobRecoveryDecision(action="resume_delivery", reason=f"claimable_outbox_after_{latest_stage}")
            if idempotency_in_progress:
                return JobRecoveryDecision(action="wait", reason="live_idempotency_lease")
            return JobRecoveryDecision(action="resume_execution", reason=f"resume_from_{latest_stage}")
        if latest_stage in self.terminal_stages:
            return JobRecoveryDecision(action="noop", reason=f"terminal_{latest_stage}")
        return JobRecoveryDecision(action="quarantine", reason=f"unknown_stage:{latest_stage}")


__all__ = [
    "CANON_JOB_RECOVERY_POLICY",
    "JobRecoveryDecision",
    "JobRecoveryPolicy",
]
