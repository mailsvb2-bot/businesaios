from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from enum import Enum

from config.live_canary_policy import LiveCanaryPolicy


class ExperimentArm(str, Enum):
    CONTROL = "control"
    CANDIDATE = "candidate"
    INELIGIBLE = "ineligible"


@dataclass(frozen=True)
class ExperimentAssignment:
    experiment_id: str
    tenant_id: str
    purpose: str
    subject_hash: str
    arm: ExperimentArm
    bucket: int
    candidate_policy_id: str
    reason: str = ""

    @property
    def eligible(self) -> bool:
        return self.arm is not ExperimentArm.INELIGIBLE


class StableExperimentAssigner:
    BUCKETS = 10_000

    def __init__(self, policy: LiveCanaryPolicy) -> None:
        self.policy = policy
        self.policy.assert_valid()
        self._secret = self.policy.assignment_secret.encode("utf-8")

    def _digest(self, *, tenant_id: str, subject_id: str) -> bytes:
        material = (
            f"live-canary@v1:{self.policy.experiment_id}:{tenant_id}:{subject_id}"
        ).encode("utf-8")
        return hmac.new(self._secret, material, hashlib.sha256).digest()

    def subject_hash(self, *, tenant_id: str, subject_id: str) -> str:
        return self._digest(tenant_id=tenant_id, subject_id=subject_id).hex()

    def bucket(self, *, tenant_id: str, subject_id: str) -> int:
        return int.from_bytes(
            self._digest(tenant_id=tenant_id, subject_id=subject_id)[:8], "big"
        ) % self.BUCKETS

    def assign(
        self,
        *,
        tenant_id: str,
        subject_id: str,
        candidate_policy_id: str,
        action: str,
        purpose: str = "live_canary",
        eligible: bool = True,
    ) -> ExperimentAssignment:
        tenant = str(tenant_id or "").strip()
        subject = str(subject_id or "").strip()
        candidate = str(candidate_policy_id or "").strip()
        action_name = str(action or "").strip()
        purpose_name = str(purpose or "").strip()

        reason = ""
        if tenant not in self.policy.allowed_tenant_ids:
            reason = "tenant_not_allowed"
        elif purpose_name not in self.policy.allowed_purposes:
            reason = "purpose_not_allowed"
        elif not bool(eligible):
            reason = "eligibility_not_proven"
        elif not subject:
            reason = "subject_id_required"
        elif not candidate:
            reason = "candidate_policy_id_required"

        if reason:
            return ExperimentAssignment(
                experiment_id=self.policy.experiment_id,
                tenant_id=tenant,
                purpose=purpose_name,
                subject_hash="",
                arm=ExperimentArm.INELIGIBLE,
                bucket=-1,
                candidate_policy_id=candidate,
                reason=reason,
            )

        bucket = self.bucket(tenant_id=tenant, subject_id=subject)
        candidate_buckets = round(self.policy.candidate_fraction * self.BUCKETS)
        arm = (
            ExperimentArm.CANDIDATE
            if bucket < candidate_buckets
            else ExperimentArm.CONTROL
        )
        if arm is ExperimentArm.CANDIDATE and action_name not in self.policy.allowed_actions:
            return ExperimentAssignment(
                experiment_id=self.policy.experiment_id,
                tenant_id=tenant,
                purpose=purpose_name,
                subject_hash=self.subject_hash(
                    tenant_id=tenant,
                    subject_id=subject,
                ),
                arm=ExperimentArm.INELIGIBLE,
                bucket=bucket,
                candidate_policy_id=candidate,
                reason="candidate_action_not_allowed",
            )
        return ExperimentAssignment(
            experiment_id=self.policy.experiment_id,
            tenant_id=tenant,
            purpose=purpose_name,
            subject_hash=self.subject_hash(tenant_id=tenant, subject_id=subject),
            arm=arm,
            bucket=bucket,
            candidate_policy_id=candidate,
        )


__all__ = ["ExperimentArm", "ExperimentAssignment", "StableExperimentAssigner"]
