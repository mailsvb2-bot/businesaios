from __future__ import annotations

import sys

sys.dont_write_bytecode = True

"""Release freeze + attestation.

Goal:
- Production deployments must be reproducible.
- In APP_ENV=prod we can optionally verify that code/config files match a
  frozen manifest (sha256) generated at release time.

Design constraints:
- Deterministic (stable ordering, stable JSON).
- No network.
- No "second brain": this module does not decide anything, only verifies.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from core.security.release_manifest_io import iter_release_files, sha256_file


@dataclass(frozen=True)
class ReleaseManifest:
    schema_version: int
    release_tag: str
    version: str
    files: dict[str, str]  # relpath -> sha256

    def to_json(self) -> str:
        obj = {
            "schema_version": int(self.schema_version),
            "release_tag": str(self.release_tag),
            "version": str(self.version),
            "files": dict(sorted(self.files.items())),
        }
        return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def generate_manifest(*, root_dir: Path, release_tag: str, version: str) -> ReleaseManifest:
    root = Path(root_dir).resolve()
    files: list[tuple[str, str]] = []
    for p in sorted(iter_release_files(root), key=lambda x: x.relative_to(root).as_posix()):
        rel = p.relative_to(root).as_posix()
        files.append((rel, sha256_file(p)))
    return ReleaseManifest(schema_version=1, release_tag=str(release_tag), version=str(version), files=dict(files))


def load_manifest(path: Path) -> ReleaseManifest:
    data = json.loads(path.read_text(encoding="utf-8"))
    return ReleaseManifest(
        schema_version=int(data.get("schema_version", 1)),
        release_tag=str(data.get("release_tag", "")),
        version=str(data.get("version", "")),
        files=dict(data.get("files", {}) or {}),
    )


def verify_manifest(*, root_dir: Path, manifest_path: Path) -> None:
    """Verify that all manifest files match.

    Raises RuntimeError on mismatch.
    """

    root = Path(root_dir).resolve()
    mp = Path(manifest_path).resolve()
    if not mp.exists():
        raise RuntimeError("RELEASE_MANIFEST_MISSING")

    m = load_manifest(mp)
    if int(m.schema_version) != 1:
        raise RuntimeError("RELEASE_MANIFEST_UNSUPPORTED_SCHEMA")

    missing: list[str] = []
    mismatched: list[str] = []

    for rel, expected in sorted(m.files.items()):
        p = root / rel
        if not p.exists():
            missing.append(rel)
            continue
        got = sha256_file(p)
        if got != str(expected):
            mismatched.append(rel)

    if missing or mismatched:
        details = {
            "missing": missing[:50],
            "mismatched": mismatched[:50],
            "missing_n": len(missing),
            "mismatched_n": len(mismatched),
        }
        raise RuntimeError("RELEASE_MANIFEST_MISMATCH:" + json.dumps(details, ensure_ascii=False, sort_keys=True))
