#!/usr/bin/env python
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

MANIFEST_PATH = pathlib.Path("release") / "manifest.json"


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="Recalculate sha256 for files listed in release/manifest.json")
    ap.add_argument("--write", action="store_true", help="Write updated hashes back to manifest.json")
    ap.add_argument("--fail-on-diff", action="store_true", help="Exit non-zero if any hash differs")
    args = ap.parse_args()

    if not MANIFEST_PATH.exists():
        print("ERROR: release/manifest.json not found", file=sys.stderr)
        return 2

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    files = manifest.get("files") or {}
    if not isinstance(files, dict):
        print("ERROR: manifest.files must be a dict", file=sys.stderr)
        return 2

    diffs = []
    updated = dict(files)
    for rel, old_hash in files.items():
        p = pathlib.Path(rel)
        if not p.exists():
            diffs.append((rel, old_hash, None))
            continue
        new_hash = sha256_file(p)
        if new_hash != old_hash:
            diffs.append((rel, old_hash, new_hash))
            updated[rel] = new_hash

    if diffs:
        for rel, old, new in diffs:
            print(f"DIFF {rel}: {old} -> {new}")
    else:
        print("OK: manifest matches files")

    if args.write and diffs:
        manifest["files"] = updated
        MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("WROTE: updated manifest.json")

    if args.fail_on_diff and diffs:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
