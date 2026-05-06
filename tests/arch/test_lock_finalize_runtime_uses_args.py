from pathlib import Path


def test_finalize_runtime_system_uses_finalize_args_dataclass():
    text = Path('runtime/boot/system_builder_finalize.py').read_text(encoding='utf-8')
    assert 'FinalizeRuntimeArgs' in text
    assert 'def finalize_runtime_system(*, args: FinalizeRuntimeArgs)' in text
