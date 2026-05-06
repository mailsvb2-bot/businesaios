import pytest

from ml.common.feature_store import FeatureStore


def test_feature_store_rejects_blank_entity_id() -> None:
    store = FeatureStore()
    with pytest.raises(ValueError):
        store.put('', {'score': 1})
