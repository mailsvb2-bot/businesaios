from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUARD = ROOT / "entrypoints" / "api" / "public_surface_security_guard.py"


def test_internal_write_replay_marker_must_be_explicit() -> None:
    text = GUARD.read_text(encoding="utf-8")

    assert "CANON_API_INTERNAL_WRITE_ADMIN_EXPLICIT_REPLAY_MARKER = True" in text
    assert "for key in ('idempotency_key', 'idempotencyKey', 'replay_nonce', 'request_nonce')" in text
    assert "return False" in text
    assert "payload.get('request_id')" not in text
    assert "metadata.get('request_id')" not in text
    assert "request_context.request_id or" not in text


def test_public_cta_remains_explicit_public_surface() -> None:
    text = GUARD.read_text(encoding="utf-8")

    assert "'/public-site/cta/start'" in text
    assert "tags=('public', 'public_site', 'cta', 'public_api')" in text
