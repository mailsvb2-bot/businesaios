from ml.scoring.base_score_model import BaseScoreModel


def test_base_score_model_handles_non_dict_features() -> None:
    model = BaseScoreModel(model_name='test_model')
    out = model.score(None)
    assert out.score == 0.5
    assert out.reasons[0] == 'test_model'
