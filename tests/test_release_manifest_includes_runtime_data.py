from __future__ import annotations

from pathlib import Path

from core.security.release_manifest import load_manifest


def test_manifest_includes_runtime_data_and_assets():
    """Production freeze must cover behavior/UX-changing runtime files."""
    root = Path(__file__).resolve().parents[1]
    mp = root / "release" / "manifest.json"
    m = load_manifest(mp)

    # Tariff catalog is runtime behavior.
    assert "data/plans.json" in m.files

    # Demo audio assets are part of the user-visible UX.
    # (We keep this minimal: at least one of the demo audio files must be frozen.)
    assert (
        "assets/audio/demo/work.opus" in m.files
        or "assets/audio/demo/home.opus" in m.files
    )
