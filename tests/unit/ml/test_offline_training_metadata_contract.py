from ml.training.offline_training import OfflineTraining


class Job:
    job_id = 'job-1'
    model_name = 'model-1'
    dataset_name = 'dataset-1'
    metadata = 'bad'


def test_offline_training_rejects_non_dict_metadata() -> None:
    result = OfflineTraining().run(Job())
    assert result.ok is False
    assert result.code == 'offline_training_metadata_must_be_dict'
