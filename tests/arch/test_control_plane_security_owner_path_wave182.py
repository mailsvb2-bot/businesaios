from __future__ import annotations

from pathlib import Path


def test_control_plane_security_owner_modules_stay_boundary_only() -> None:
    for relative in (
        'entrypoints/api/control_plane_security_guard.py',
        'entrypoints/api/webhook_security_surface_guard.py',
    ):
        text = Path(relative).read_text(encoding='utf-8')
        lowered = text.lower()
        assert 'decisioncore' not in text
        assert 'second brain' not in lowered
        assert 'from core.ai' not in text
        assert 'from application.decision' not in text


def test_control_plane_routes_use_canonical_security_owner() -> None:
    text = Path('adapters/api/fastapi/control_plane_routes.py').read_text(encoding='utf-8')
    assert 'ControlPlaneSecurityGuard' in text
    assert 'enforce_control_plane_security' in text
