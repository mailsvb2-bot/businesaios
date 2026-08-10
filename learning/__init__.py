from .registry import (
    ArtifactRegistry,
    ModelArtifact,
    ModelRegistry,
    ValidatedModelRecord,
    build_model_registry,
)
from .trainer import (
    DatasetBuilder,
    DatasetSnapshot,
    OfflineTrainer,
    PolicyMeanScore,
    PolicyValidator,
    PolicyValidatorV14,
    TrainResult,
    TrainingJob,
    OfflineTraining,
    TrainingValidation,
    ValidationReport,
    ValidationScoreView,
    ValidationVerdict,
    build_validation_score_view,
    score_policies,
)
from .replay import (
    Event,
    EventStore,
    FeedbackLoopFirewall,
    OfflineReplayEvaluator,
    FeedbackLoopViolation,
    EvaluationResult,
    PolicyMetadata,
    EvaluationSample,
    OfflineEventStore,
    PolicyDatasetSplitter,
    PolicyEvaluator,
    RuntimeEventStoreAdapter,
    SplitResult,
)
from .policy_update import (
    EvaluationSnapshot,
    OnlineUpdate,
    PolicyPromotionGuard,
    PromotionBlocked,
    PromotionDecision,
)
from .rollout import (
    PolicyRollout,
    RolloutDecision,
    RolloutGuard,
    PolicyRolloutManager,
    RolloutGuardViolation,
    RolloutManager,
    RolloutState,
)
from .outcome_math import OutcomeMathSupport

# Preserve the historical package-level submodule attributes explicitly.
# The submodules are already loaded by the public imports above; redundant aliases
# make the compatibility surface visible to static analysis without changing init order.
from . import outcome_math as outcome_math
from . import policy_update as policy_update
from . import registry as registry
from . import replay as replay
from . import rollout as rollout
from . import trainer as trainer

__all__ = [
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
