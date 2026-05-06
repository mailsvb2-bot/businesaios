from __future__ import annotations

import importlib


def test_runtime_config_aliases_resolve_without_shim_files() -> None:
    settings_loader = importlib.import_module("runtime.config.settings_loader")
    feature_flags = importlib.import_module("runtime.config.feature_flags")
    runtime_config = importlib.import_module("runtime.config")

    assert settings_loader is runtime_config
    assert feature_flags is runtime_config
    assert hasattr(settings_loader, "load_settings")
    assert hasattr(feature_flags, "FeatureFlags")



def test_event_store_sqlite_user_state_alias_resolves_directly() -> None:
    legacy_module = importlib.import_module("runtime.platform.event_store._sqlite_user_state")
    canonical_module = importlib.import_module("runtime.platform.event_store.sqlite_user_state")

    assert legacy_module is canonical_module
    assert legacy_module.get_user_state is canonical_module.get_user_state
    assert legacy_module.project_user_state is canonical_module.project_user_state
    assert legacy_module.delete_user_events is canonical_module.delete_user_events
