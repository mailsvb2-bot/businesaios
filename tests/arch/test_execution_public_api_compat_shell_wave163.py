from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_execution_public_api_is_now_a_package_owned_alias() -> None:
    text = (ROOT / "execution" / "__init__.py").read_text(encoding="utf-8")
    assert 'The package root is the single execution owner surface.' in text
    assert 'install_public_api_alias(__name__)' in text
    assert 'CANON_EXECUTION_PUBLIC_API_COMPAT_SHELL = True' in text
    assert not (ROOT / 'execution' / 'public_api.py').exists()
