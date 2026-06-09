"""Release packager (canonical runtime artifact).

Goal:
- produce a clean runtime release ZIP
- exclude dev-only surfaces and volatile local state
- keep one canonical file-selection policy shared with manifest generation and CI

Usage:
    python scripts/package_release.py [output.zip]
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_OUTPUT = ROOT.parent / 'BUSINESAIOS_RUNTIME_RELEASE.zip'


def _resolve_output(argv: list[str]) -> Path:
    if len(argv) > 2:
        raise SystemExit('usage: python scripts/package_release.py [output.zip]')
    if len(argv) == 2:
        return Path(argv[1]).resolve()
    return DEFAULT_OUTPUT.resolve()


def build_release_zip(*, repo_root: Path, out_zip: Path) -> int:
    from core.security.release_runtime_surface import iter_runtime_release_files

    repo_root = Path(repo_root).resolve()
    out_zip = Path(out_zip).resolve()
    files = [(path.relative_to(repo_root).as_posix(), path) for path in iter_runtime_release_files(repo_root)]

    out_zip.parent.mkdir(parents=True, exist_ok=True)
    if out_zip.exists():
        out_zip.unlink()

    with zipfile.ZipFile(out_zip, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel, path in files:
            zf.write(path, rel)

    with zipfile.ZipFile(out_zip, 'r') as zf:
        bad = zf.testzip()
        if bad is not None:
            raise RuntimeError(f'release zip integrity failure at {bad}')

    print(f'OK: wrote {out_zip} ({len(files)} files)')
    return 0


def main(argv: list[str] | None = None) -> int:
    return build_release_zip(repo_root=ROOT, out_zip=_resolve_output(argv or sys.argv))


if __name__ == '__main__':
    raise SystemExit(main())
