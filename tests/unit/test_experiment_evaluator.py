from experimentation.experiment_evaluator import ExperimentEvaluator


def test_experiment_evaluator_returns_result():
    result = ExperimentEvaluator().evaluate({'experiment_id': 'e1'})
    assert result['kind'] == 'experiment_result'
