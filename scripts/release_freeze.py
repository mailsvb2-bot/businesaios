from __future__ import annotations

"""Create/refresh a production release manifest.

Usage:
  python scripts/release_freeze.py --tag v17.0.0 --version 17.0.0

This script is deterministic and safe to run locally.
"""

import argparse
from pathlib import Path
import sys
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.security.release_manifest import generate_manifest  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True, help="Release tag (e.g. v17.0.0)")
    ap.add_argument("--version", required=True, help="Human version (e.g. 17.0.0)")
    args = ap.parse_args()

    root = ROOT
    release_dir = root / "release"
    release_dir.mkdir(parents=True, exist_ok=True)

    (root / "RELEASE_TAG").write_text(str(args.tag).strip() + "\n", encoding="utf-8")
    (root / "VERSION").write_text(str(args.version).strip() + "\n", encoding="utf-8")

    manifest = generate_manifest(root_dir=root, release_tag=args.tag, version=args.version)
    (release_dir / "manifest.json").write_text(manifest.to_json() + "\n", encoding="utf-8")

    print("Wrote:")
    print(" -", (root / "VERSION").as_posix())
    print(" -", (root / "RELEASE_TAG").as_posix())
    print(" -", (release_dir / "manifest.json").as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
