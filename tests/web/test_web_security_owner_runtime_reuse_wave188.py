from app.web.app import WebApp
from entrypoints.api.security_owner_bundle import ApiSecurityOwnerBundle
from runtime.runtime_infra import RuntimeInfra


def test_web_app_reuses_explicit_security_owner_bundle(tmp_path) -> None:
    bundle = ApiSecurityOwnerBundle.default(audit_path=tmp_path / 'api_security.jsonl')
    app = WebApp(security_owner_bundle=bundle)
    assert app._resolved_security_adapter() is bundle.adapter


def test_web_app_reuses_runtime_infra_security_owner_bundle(tmp_path) -> None:
    bundle = ApiSecurityOwnerBundle.default(audit_path=tmp_path / 'api_security.jsonl')
    app = WebApp(runtime_infra=RuntimeInfra(api_security_owner_bundle=bundle))
    assert app._resolved_security_adapter() is bundle.adapter
