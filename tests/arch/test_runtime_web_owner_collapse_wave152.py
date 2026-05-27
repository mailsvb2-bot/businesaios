from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding='utf-8')


def test_runtime_web_modules_do_not_use_retired_public_api_leaves() -> None:
    relpaths = [
        'runtime/boot/system_builder_finalize.py',
        'runtime/boot/web/messaging_policy_dashboard_boot.py',
        'runtime/boot/web/runtime_web_service_builders.py',
        'runtime/boot/web/runtime_web_attach.py',
        'runtime/boot/web/runtime_web_bundle_factory.py',
    ]
    for relpath in relpaths:
        content = _read(relpath)
        assert 'runtime.boot.web.public_api_bundles' not in content
        assert 'runtime.boot.web.public_api_graphs' not in content
        assert 'runtime.boot.web.public_api_observability' not in content
        assert 'runtime.boot.web.public_api_runtime' not in content
        assert 'runtime.boot.web.public_api_settings' not in content
