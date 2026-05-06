from learning import policy_update, replay, rollout, trainer
from learning import registry


def test_learning_contract_surfaces_are_centered_in_four_modules():
    assert hasattr(trainer, "DatasetBuilder")
    assert hasattr(trainer, "OfflineTrainer")
    assert hasattr(trainer, "PolicyValidator")
    assert hasattr(registry, "ArtifactRegistry")
    assert hasattr(registry, "ModelRegistry")
    assert hasattr(replay, "RuntimeEventStoreAdapter")
    assert hasattr(replay, "PolicyDatasetSplitter")
    assert hasattr(replay, "PolicyEvaluator")
    assert hasattr(policy_update, "PolicyPromotionGuard")
    assert hasattr(policy_update, "OnlineUpdate")
    assert hasattr(rollout, "RolloutManager")
    assert hasattr(rollout, "PolicyRolloutManager")
