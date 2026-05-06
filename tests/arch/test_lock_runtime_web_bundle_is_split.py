from pathlib import Path


def test_runtime_web_bundle_remains_thin():
    text = Path('runtime/boot/web/runtime_web_bundle.py').read_text(encoding='utf-8')
    assert 'boot_runtime_web_bundle_fastapi' in text
    assert 'boot_runtime_web_bundle_flask' in text
    assert 'MessagingPolicyObservabilityBootFlags' not in text
    assert 'boot_messaging_policy_observability_fastapi' not in text
    assert 'boot_messaging_policy_observability_flask' not in text


def test_runtime_web_package_init_is_thin():
    text = Path('runtime/boot/web/__init__.py').read_text(encoding='utf-8').strip()
    assert 'public_api' in text
    assert 'runtime_web_attach import attach_runtime_web_bundle' not in text
    assert 'boot_messaging_policy_snapshot_fastapi' not in text
