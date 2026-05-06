from pathlib import Path


def test_runtime_web_attachment_propagates_shared_security_owner_bundle() -> None:
    attach_text = Path("runtime/boot/web/runtime_web_attach.py").read_text(encoding="utf-8")
    finalize_text = Path("runtime/boot/system_builder_finalize.py").read_text(encoding="utf-8")

    assert "api_security_owner_bundle" in attach_text
    assert "_resolve_runtime_web_security_owner_bundle" in attach_text
    assert "api_security_owner_bundle=getattr(args.runtime_infra, \"api_security_owner_bundle\", None)" in finalize_text
