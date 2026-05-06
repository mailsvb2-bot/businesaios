from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_runtime_web_attach_uses_split_helpers_not_inline_setattr_block():
    path = PROJECT_ROOT / 'runtime' / 'boot' / 'web' / 'runtime_web_attach.py'
    text = path.read_text(encoding='utf-8')
    assert 'build_runtime_web_bundle' in text
    assert 'build_runtime_web_attachment_attrs' in text
    assert 'iter_runtime_web_targets' in text
    assert 'apply_runtime_web_attachment' in text
    assert text.count('setattr(') == 0
