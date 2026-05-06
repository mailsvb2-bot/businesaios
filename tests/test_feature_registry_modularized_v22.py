from core.marketing.feature_registry_200 import FEATURES_200, feature_map


def test_feature_registry_split_preserves_unique_features() -> None:
    names = [f.name for f in FEATURES_200]
    assert len(names) >= 100
    assert len(names) == len(set(names))
    fmap = feature_map()
    assert set(fmap.keys()) == set(names)
