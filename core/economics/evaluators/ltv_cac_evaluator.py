from __future__ import annotations

from dataclasses import dataclass, field

from config.economics_evaluation_policy import (
    DEFAULT_LTV_CAC_EVALUATOR_POLICY,
    LTVCACEvaluatorPolicy,
)

from ..enums import EconomicsSignalStatus
from ..types import CACSnapshot, LTVSnapshot


@dataclass
class LTVCACEvaluator:
    policy: LTVCACEvaluatorPolicy = field(default_factory=lambda: DEFAULT_LTV_CAC_EVALUATOR_POLICY)

    def evaluate(self, ltv: LTVSnapshot, cac: CACSnapshot) -> EconomicsSignalStatus:
        if ltv.ltv is None or cac.blended_cac is None or cac.blended_cac <= 0:
            return EconomicsSignalStatus.UNKNOWN
        ratio = ltv.ltv / cac.blended_cac
        if ratio >= self.policy.healthy_ratio_threshold:
            return EconomicsSignalStatus.HEALTHY
        if ratio >= self.policy.warning_ratio_threshold:
            return EconomicsSignalStatus.WARNING
        return EconomicsSignalStatus.CRITICAL
