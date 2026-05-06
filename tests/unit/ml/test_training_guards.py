from ml.training.offline_training import OfflineTraining
from ml.training.online_update import OnlineUpdate
from ml.training.training_jobs import TrainingJob


def test_offline_training_requires_dataset_name() -> None:
    result = OfflineTraining().run(TrainingJob(job_id='j1', model_name='model', dataset_name=''))
    assert result.ok is False


def test_online_update_requires_dict_observations() -> None:
    result = OnlineUpdate().apply('model', [{} , 'bad'])
    assert result.ok is False
