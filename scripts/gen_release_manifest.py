from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    release_tag = (root / "RELEASE_TAG").read_text(encoding="utf-8").strip() if (root / "RELEASE_TAG").exists() else "dev"
    version = (root / "VERSION").read_text(encoding="utf-8").strip() if (root / "VERSION").exists() else "0"

    from core.security.release_manifest import generate_manifest

    m = generate_manifest(root_dir=root, release_tag=release_tag, version=version)
    out = root / "release" / "manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(m.to_json() + "\n", encoding="utf-8")
    print(f"[ok] wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
