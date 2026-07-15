from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.lock
def test_staging_runtime_proof_supplies_production_control_plane_auth() -> None:
    root = Path(__file__).resolve().parents[2]
    script = (root / "scripts" / "staging" / "run_staging_runtime_proof.sh").read_text(encoding="utf-8")

    required = (
        'CONTROL_PLANE_API_KEY_PEPPER="${API_CONTROL_PLANE_API_KEY_PEPPER:-}"',
        "secrets.token_urlsafe(48)",
        'CONTROL_PLANE_API_KEY_STORE_PATH="${BAIOS_STAGING_API_KEY_STORE_PATH:-/app/data/api/api_keys.json}"',
        '-e API_CONTROL_PLANE_ALLOW_DEV_FALLBACKS=0 \\',
        '-e API_CONTROL_PLANE_API_KEY_PEPPER="$CONTROL_PLANE_API_KEY_PEPPER" \\',
        '-e BUSINESAIOS_API_KEY_STORE_BACKEND=file \\',
        '-e BUSINESAIOS_API_KEY_STORE_PATH="$CONTROL_PLANE_API_KEY_STORE_PATH" \\',
    )
    missing = [snippet for snippet in required if snippet not in script]

    assert not missing, f"staging runtime proof misses production auth wiring: {missing}"
    assert 'echo "$CONTROL_PLANE_API_KEY_PEPPER"' not in script
