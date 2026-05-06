from learning.policy_update import PolicyPromotionGuard as CanonPolicyPromotionGuard
from learning.replay import PolicyDatasetSplitter as CanonPolicyDatasetSplitter
from learning.rollout import PolicyRolloutManager as CanonPolicyRolloutManager
from learning.trainer import DatasetBuilder as CanonDatasetBuilder
from learning.trainer import OfflineTrainer as CanonOfflineTrainer
from learning.trainer import PolicyValidator as CanonPolicyValidator
from ml.dataset_builder import DatasetBuilder
from ml.datasets.policy_dataset_splitter import PolicyDatasetSplitter
from learning.trainer import OfflineTrainer
from ml.policy_promotion_guard import PolicyPromotionGuard
from ml.policy_rollout_manager import PolicyRolloutManager
from learning.trainer import PolicyValidator


def test_ml_wrappers_resolve_to_learning_core_classes():
    assert DatasetBuilder is CanonDatasetBuilder
    assert OfflineTrainer is CanonOfflineTrainer
    assert PolicyValidator is CanonPolicyValidator
    assert PolicyDatasetSplitter is CanonPolicyDatasetSplitter
    assert PolicyPromotionGuard is CanonPolicyPromotionGuard
    assert PolicyRolloutManager is CanonPolicyRolloutManager
