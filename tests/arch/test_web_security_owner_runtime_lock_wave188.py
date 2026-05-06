from pathlib import Path


def test_runtime_infra_exposes_api_security_owner_bundle_field() -> None:
    text = Path('runtime/runtime_infra.py').read_text(encoding='utf-8')
    assert 'api_security_owner_bundle: Any = None' in text


def test_web_app_resolves_shared_runtime_security_owner_before_fallback() -> None:
    text = Path('app/web/app.py').read_text(encoding='utf-8')
    assert 'security_owner_bundle: ApiSecurityOwnerBundle | None = None' in text
    assert "runtime_bundle = getattr(self.runtime_infra, 'api_security_owner_bundle', None)" in text
    assert 'return self._default_security_adapter()' in text
