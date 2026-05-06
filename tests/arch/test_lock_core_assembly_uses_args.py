from pathlib import Path


def test_core_assembly_uses_core_assembly_args():
    text = Path('runtime/boot/boot_core_assembly.py').read_text(encoding='utf-8')
    assert 'CoreAssemblyArgs' in text
    assert 'def build_core_assembly(*, args: CoreAssemblyArgs)' in text
