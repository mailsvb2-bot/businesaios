from __future__ import annotations

import fnmatch
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "release" / "manifest.json"


FORBIDDEN_DIRS = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}

FORBIDDEN_FILE_GLOBS = {
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.so",
    "*.dylib",
    "*.dll",
    ".DS_Store",
}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_forbidden_file(name: str) -> bool:
    return any(fnmatch.fnmatch(name, pat) for pat in FORBIDDEN_FILE_GLOBS)


def _iter_repo_files() -> list[str]:
    """Return all repo files as POSIX relative paths (excluding release/manifest.json)."""
    out: list[str] = []
    for p in ROOT.rglob("*"):
        rel = p.relative_to(ROOT).as_posix()
        if rel == "release/manifest.json":
            continue
        if p.is_dir():
            if p.name in FORBIDDEN_DIRS:
                raise AssertionError(f"Forbidden directory present: {rel}")
            continue
        if _is_forbidden_file(p.name):
            raise AssertionError(f"Forbidden artifact file present: {rel}")
        if set(p.parts) & FORBIDDEN_DIRS:
            raise AssertionError(f"Forbidden artifact path present: {rel}")
        out.append(rel)
    return sorted(out)


def test_release_gate_no_artifacts_and_manifest_in_sync() -> None:
    assert MANIFEST_PATH.exists(), "release/manifest.json must exist"
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    files = manifest.get("files")
    assert isinstance(files, dict) and files, "manifest.json must contain non-empty 'files' map"

    # Global artifact check (must never be present anywhere in the repo)
    # NOTE: We do *not* require the manifest to enumerate every file in the repo.
    # It is an attestation list for the release packaging surface.
    _iter_repo_files()

    # Manifest integrity check: every referenced file exists and matches sha256.
    missing = []
    for rel in sorted(files.keys()):
        p = ROOT / rel
        if not p.exists() or not p.is_file():
            missing.append(rel)
    assert not missing, "manifest references missing files:\n  - " + "\n  - ".join(missing)

    mismatched: list[str] = []
    for rel, expected_sha in sorted(files.items()):
        p = ROOT / rel
        got = _sha256_file(p)
        if got != expected_sha:
            mismatched.append(f"{rel} expected={expected_sha} got={got}")
    assert not mismatched, "manifest sha256 mismatch:\n  - " + "\n  - ".join(mismatched)

    # Tenant audit is part of release gate (prevents silent multi-tenant corruption).
    from scripts.audit_tenant_usage import audit as audit
    assert audit(str(ROOT)) == 0
