from __future__ import annotations

class ActionGuard:
    def allows(self, payload: dict) -> bool:
        return not bool(payload.get("action_blocked", False))

class CheckpointGuard:
    def allows(self, payload: dict) -> bool:
        return not bool(payload.get("checkpoint_blocked", False))

class DatasetGuard:
    def allows(self, payload: dict) -> bool:
        return not bool(payload.get("dataset_blocked", False))

class PolicyGuard:
    def allows(self, payload: dict) -> bool:
        return not bool(payload.get("policy_blocked", False))

class PromotionGuard:
    def allows(self, payload: dict) -> bool:
        return bool(
            payload.get("evaluation_passed", False)
            and payload.get("safety_passed", False)
            and payload.get("approved", False)
        )

class RewardGuard:
    def allows(self, payload: dict) -> bool:
        return not bool(payload.get("reward_hacking_detected", False))

class RolloutGuard:
    def allows(self, payload: dict) -> bool:
        return not bool(payload.get("rollout_blocked", False))

class ServingGuard:
    def allows(self, payload: dict) -> bool:
        return not bool(payload.get("serving_blocked", False))

class TrainingGuard:
    def allows(self, payload: dict) -> bool:
        return not bool(payload.get("training_blocked", False))

__all__ = [
    "ActionGuard",
    "CheckpointGuard",
    "DatasetGuard",
    "PolicyGuard",
    "PromotionGuard",
    "RewardGuard",
    "RolloutGuard",
    "ServingGuard",
    "TrainingGuard",
]

_MODULE_EXPORTS = {
    "action_guard": {"ActionGuard": f"{__name__}:ActionGuard"},
    "checkpoint_guard": {"CheckpointGuard": f"{__name__}:CheckpointGuard"},
    "dataset_guard": {"DatasetGuard": f"{__name__}:DatasetGuard"},
    "policy_guard": {"PolicyGuard": f"{__name__}:PolicyGuard"},
    "promotion_guard": {"PromotionGuard": f"{__name__}:PromotionGuard"},
    "reward": {"RewardGuard": f"{__name__}:RewardGuard"},
    "reward_guard": {"RewardGuard": f"{__name__}:RewardGuard"},
    "rollout_guard": {"RolloutGuard": f"{__name__}:RolloutGuard"},
    "serving_guard": {"ServingGuard": f"{__name__}:ServingGuard"},
    "training_guard": {"TrainingGuard": f"{__name__}:TrainingGuard"},
}
