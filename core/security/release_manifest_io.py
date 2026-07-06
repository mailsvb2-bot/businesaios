from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path

from core.security.release_runtime_surface import is_runtime_release_excluded

INCLUDE_SUFFIXES = {
    '.py',
    '.txt',
    '.md',
    '.yaml',
    '.yml',
    '.json',
    '.toml',
    '.ini',
    '.cfg',
    '.css',
    '.js',
    '.sql',
    '.example',
    '.fragment',
    '.public_api',
    '.platform',
    '.sample',
    '.service',
    '.opus',
    '.ogg',
}

INCLUDE_NAMES = {
    'requirements.lock.txt',
    'requirements.optional.txt',
    'requirements.txt',
    'VERSION',
    'RELEASE_TAG',
    '.gitignore',
}

MANIFEST_ONLY_EXCLUDE_DIR_NAMES = {
    'analytics',
}

MANIFEST_ONLY_EXCLUDE_EXACT = {
    'interfaces/ads/meta_connector.py',
    'interfaces/ads/tiktok_ads_connector.py',
}



def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()



def _is_excluded(rel: str, path: Path) -> bool:
    if rel == 'release/manifest.json':
        return True
    if is_runtime_release_excluded(rel, path):
        return True
    if rel in MANIFEST_ONLY_EXCLUDE_EXACT:
        return True
    if any(part in MANIFEST_ONLY_EXCLUDE_DIR_NAMES for part in Path(rel).parts):
        return True
    return False



def iter_release_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob('*'), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_dir():
            continue
        rel = path.relative_to(root).as_posix()
        if _is_excluded(rel, path):
            continue
        if path.suffix in INCLUDE_SUFFIXES or path.name in INCLUDE_NAMES:
            yield path
