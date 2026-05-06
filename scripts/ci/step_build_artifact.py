from __future__ import annotations

import zipfile

from scripts.ci.artifact_manifest import iter_project_files, sha256_file
from scripts.ci.paths import dist_dir, repo_root


def _version() -> str:
    version_file = repo_root() / "VERSION"
    if version_file.exists():
        value = version_file.read_text(encoding="utf-8").strip()
        if value:
            return value
    return "0.0.0"


def run() -> tuple[bool, str]:
    root = repo_root()
    dist = dist_dir()
    version = _version()
    artifact = dist / f"BUSINESAIOS_{version}_release.zip"

    with zipfile.ZipFile(artifact, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in iter_project_files(root):
            if dist in path.parents:
                continue
            rel = path.relative_to(root)
            zf.write(path, rel.as_posix())

    digest = sha256_file(artifact)
    (dist / f"{artifact.name}.sha256").write_text(
        f"{digest}  {artifact.name}\n",
        encoding="utf-8",
    )

    return True, f"artifact built: {artifact.name}"
