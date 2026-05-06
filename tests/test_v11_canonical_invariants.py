from pathlib import Path


def test_runtime_application_stays_single_owner() -> None:
    text = Path("runtime/application/__init__.py").read_text(encoding="utf-8")
    assert 'CANON_RUNTIME_APPLICATION_PACKAGE_OWNER = True' in text
    assert 'from runtime.application.contracts import (' in text


def test_core_decision_public_api_is_now_package_owned_alias() -> None:
    text = Path("core/decision/__init__.py").read_text(encoding="utf-8")
    assert 'CANONICAL_OWNER_PUBLIC_API = "core.decision"' in text
    assert 'install_public_api_alias(__name__)' in text
    assert not Path('core/decision/public_api.py').exists()
