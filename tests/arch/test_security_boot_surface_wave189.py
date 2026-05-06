from pathlib import Path


def test_runtime_boot_surface_carries_security_surface_and_shared_runtime_payload() -> None:
    text = Path('bootstrap/runtime_boot.py').read_text(encoding='utf-8')
    assert 'security_surface: SecurityBootSurface' in text
    assert 'def shared_runtime_payload(self)' in text
