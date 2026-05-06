from pathlib import Path


def test_runtime_public_api_delegates_directly_to_sovereign_bootstrap_owner() -> None:
    text = Path("boot/runtime_public_api.py").read_text(encoding="utf-8")
    assert "CANON_RUNTIME_PUBLIC_API_DIRECT_OWNER_BOOTSTRAP = True" in text
    assert 'from runtime.bootstrap import bootstrap_runtime' not in text
    assert 'runtime.bootstrap.sovereign_bootstrap' not in text
    assert 'getattr(import_module("runtime.bootstrap"), "bootstrap_runtime")' in text
    assert 'return _bootstrap_runtime_owner()(project_root=project_root).artifacts.built_runtime' in text
