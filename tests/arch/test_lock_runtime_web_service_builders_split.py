from pathlib import Path


def test_runtime_web_service_builders_is_owned_single_module() -> None:
    path = Path(__file__).resolve().parents[2] / 'runtime' / 'boot' / 'web' / 'runtime_web_service_builders.py'
    text = path.read_text(encoding='utf-8')
    assert 'class RuntimeWebSettingsParts' in text
    assert 'class RuntimeWebSnapshotParts' in text
    assert 'class RuntimeWebEventParts' in text
    assert 'build_messaging_policy_service_graph' in text
    assert 'build_messaging_preferences_bundle' in text
