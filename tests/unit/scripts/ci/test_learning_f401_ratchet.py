from __future__ import annotations

import learning
from scripts.ci.step_quality import _RATCHETED_STRICT_DEBT

_EXPECTED_PUBLIC_EXPORTS = [
    'registry',
    'ArtifactRegistry',
    'ModelArtifact',
    'ModelRegistry',
    'ValidatedModelRecord',
    'build_model_registry',
    'replay',
    'outcome_math',
    'trainer',
    'DatasetBuilder',
    'DatasetSnapshot',
    'OfflineTrainer',
    'PolicyMeanScore',
    'PolicyValidator',
    'PolicyValidatorV14',
    'TrainResult',
    'TrainingJob',
    'OfflineTraining',
    'TrainingValidation',
    'ValidationReport',
    'ValidationScoreView',
    'ValidationVerdict',
    'build_validation_score_view',
    'score_policies',
    'Event',
    'EventStore',
    'FeedbackLoopFirewall',
    'OfflineReplayEvaluator',
    'FeedbackLoopViolation',
    'EvaluationResult',
    'PolicyMetadata',
    'EvaluationSample',
    'OfflineEventStore',
    'PolicyDatasetSplitter',
    'PolicyEvaluator',
    'RuntimeEventStoreAdapter',
    'SplitResult',
    'policy_update',
    'EvaluationSnapshot',
    'OnlineUpdate',
    'PolicyPromotionGuard',
    'PromotionBlocked',
    'PromotionDecision',
    'rollout',
    'PolicyRollout',
    'RolloutDecision',
    'RolloutGuard',
    'PolicyRolloutManager',
    'RolloutGuardViolation',
    'RolloutManager',
    'RolloutState',
    'OutcomeMathSupport',
]


def test_learning_f401_debt_cannot_regrow() -> None:
    assert ('learning', 'F401') in _RATCHETED_STRICT_DEBT


def test_learning_package_public_exports_are_preserved() -> None:
    assert learning.__all__ == _EXPECTED_PUBLIC_EXPORTS
    for name in _EXPECTED_PUBLIC_EXPORTS:
        assert hasattr(learning, name)
