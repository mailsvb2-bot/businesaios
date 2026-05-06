from ml.common.feature_store import FeatureStore


def test_feature_store_require_raises_for_missing_entity() -> None:
    store = FeatureStore()
    try:
        store.require('missing')
    except KeyError as exc:
        assert str(exc).strip("'") == 'missing'
    else:
        raise AssertionError('expected missing feature vector')
