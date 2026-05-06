from __future__ import annotations

from pathlib import Path


FORBIDDEN_LITERALS = (
    'change-me-control-plane-secret',
    'dev-control-plane-secret',
    'dev-control-plane',
)


def test_api_control_plane_has_no_hardcoded_secrets() -> None:
    text = Path('interfaces/api/fastapi_router_adapter.py').read_text(encoding='utf-8')
    for literal in FORBIDDEN_LITERALS:
        assert literal not in text
