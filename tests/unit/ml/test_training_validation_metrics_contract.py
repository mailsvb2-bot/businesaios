from ml.training.validation import TrainingValidation


def test_training_validation_rejects_non_dict_metrics() -> None:
    ok, issues = TrainingValidation().validate_metrics(None)
    assert ok is False
    assert issues == ['metrics_must_be_dict']
