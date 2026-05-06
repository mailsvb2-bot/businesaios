from ml.training.offline_training import OfflineTraining
from ml.training.training_jobs import TrainingJob


def test_offline_training_rejects_non_string_metadata_values() -> None:
    result = OfflineTraining().run(TrainingJob(job_id='j1', model_name='m1', dataset_name='d1', metadata={'folds': 5}))
    assert result.ok is False
    assert result.code == 'offline_training_metadata_values_must_be_strings'
