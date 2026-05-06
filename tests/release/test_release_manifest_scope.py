from __future__ import annotations

from pathlib import Path

from core.security.release_manifest import load_manifest


ROOT = Path(__file__).resolve().parents[2]


def test_manifest_excludes_dev_only_surfaces() -> None:
    manifest = load_manifest(ROOT / 'release' / 'manifest.json')
    for prefix in ('tests/', 'docs/', 'examples/', 'scripts/', 'ci/', '.github/'):
        assert not any(rel.startswith(prefix) for rel in manifest.files), prefix
