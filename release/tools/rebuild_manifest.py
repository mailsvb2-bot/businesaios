from __future__ import annotations

import json
from pathlib import Path

from core.security.release_manifest import generate_manifest, load_manifest


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "release" / "manifest.json"


def main() -> int:
    if not MANIFEST.exists():
        raise SystemExit(f"manifest not found: {MANIFEST}")

    current = load_manifest(MANIFEST)
    rebuilt = generate_manifest(root_dir=ROOT, release_tag=current.release_tag, version=current.version)

    payload = json.dumps(
        {
            "schema_version": int(rebuilt.schema_version),
            "release_tag": str(rebuilt.release_tag),
            "version": str(rebuilt.version),
            "files": dict(sorted(rebuilt.files.items())),
        },
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    MANIFEST.write_text(payload, encoding="utf-8")
    print(f"[ok] rebuilt manifest with {len(rebuilt.files)} files in {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
