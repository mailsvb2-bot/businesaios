from __future__ import annotations

from dataclasses import dataclass, field

from governance.economic.action_economics_model import ActionEconomicsAssessment, ActionEconomicsIntent, ActionEconomicsSnapshot
from governance.economic.economic_policy_contract import EconomicPolicyConfig, PolicyCheckResult

CANON_NON_DECISION_MODULE = True


@dataclass(frozen=True)
class StopLossPolicy:
    config: EconomicPolicyConfig = field(default_factory=EconomicPolicyConfig)

    def evaluate(self, *, intent: ActionEconomicsIntent, assessment: ActionEconomicsAssessment, snapshot: ActionEconomicsSnapshot) -> PolicyCheckResult:
        if snapshot.open_stop_loss_flags:
            return PolicyCheckResult(
                policy_name='stop_loss_policy',
                status='veto',
                reason=f'stop_loss_veto:{snapshot.open_stop_loss_flags[0]}',
                details={'open_stop_loss_flags': snapshot.open_stop_loss_flags},
            )
        if float(snapshot.drawdown_ratio) >= float(self.config.max_drawdown_ratio):
            return PolicyCheckResult(
                policy_name='stop_loss_policy',
                status='veto',
                reason='stop_loss_veto:max_drawdown_reached',
                details={
                    'drawdown_ratio': float(snapshot.drawdown_ratio),
                    'max_drawdown_ratio': float(self.config.max_drawdown_ratio),
                    'action_type': intent.action_type,
                    'channel': intent.channel,
                },
            )
        if self.config.block_negative_roi and self.config.negative_roi_veto and assessment.expected_roi < 0.0:
            return PolicyCheckResult(
                policy_name='stop_loss_policy',
                status='veto',
                reason='stop_loss_veto:negative_roi',
                details={'expected_roi': assessment.expected_roi, 'action_type': intent.action_type, 'channel': intent.channel},
            )
        return PolicyCheckResult(
            policy_name='stop_loss_policy',
            status='allow',
            reason='stop_loss_ok',
            details={
                'expected_roi': assessment.expected_roi,
                'drawdown_ratio': float(snapshot.drawdown_ratio),
            },
        )
