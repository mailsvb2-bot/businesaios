from runtime.platform.config.feature_flags import FeatureFlags
from runtime.platform.config.settings_loader import load_settings
from runtime.platform.config.yaml_loader import load_yaml


def test_canonical_config_layer_imports():
    assert callable(load_settings)
    assert hasattr(FeatureFlags, "is_enabled")
    assert callable(load_yaml)
