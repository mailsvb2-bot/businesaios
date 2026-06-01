from learning import policy_update, registry, replay, rollout, trainer


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


def test_model_registry_validated_candidate_contract_is_shared_by_memory_and_file_backends(tmp_path):
    file_registry = registry.ModelRegistry(tmp_path / "models")
    file_artifact = file_registry.register_artifact(
        snapshot_id="snapshot-1",
        algo="best_policy_by_mean_reward_v1",
        metrics={"n": 150.0, "offline_mean_reward": 1.5},
        payload={"best_policy_id": "policy.file"},
    )
    file_record = file_registry.mark_validated(model=file_artifact, validation={"passed": True})
    assert file_record.candidate_policy_id == "policy.file"
    assert file_registry.latest_validated().candidate_policy_id == "policy.file"

    memory_registry = registry.ArtifactRegistry()
    memory_artifact = memory_registry.register_artifact(
        snapshot_id="snapshot-2",
        algo="best_policy_by_mean_reward_v1",
        metrics={"n": 150.0, "offline_mean_reward": 2.5},
        payload={"best_policy_id": "policy.memory"},
    )
    memory_record = memory_registry.mark_validated(model=memory_artifact, validation={"passed": True})
    assert memory_record.candidate_policy_id == "policy.memory"
    assert memory_registry.latest_validated().candidate_policy_id == "policy.memory"
