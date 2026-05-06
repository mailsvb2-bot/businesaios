from entrypoints.api.security_owner_bundle import ApiSecurityOwnerBundle


def test_security_owner_bundle_shares_single_adapter_across_guards() -> None:
    bundle = ApiSecurityOwnerBundle.default(audit_path='runtime/data/security/test_wave184_api_owner_audit.jsonl')

    assert bundle.api_surface_guard.adapter is bundle.adapter
    assert bundle.public_surface_guard.adapter is bundle.adapter
    assert bundle.webhook_surface_guard.adapter is bundle.adapter
    assert bundle.control_plane_guard.security_guard is bundle.api_surface_guard
