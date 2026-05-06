from pathlib import Path


def test_runtime_web_attach_is_single_owner_module():
    text = Path('runtime/boot/web/runtime_web_attach.py').read_text(encoding='utf-8')
    assert 'def build_runtime_web_attach_core_attrs' in text
    assert 'def build_runtime_web_attach_service_attrs' in text
    assert 'def build_runtime_web_attach_bundle_attrs' in text
    assert 'def build_runtime_web_attachment_attrs' in text
