from __future__ import annotations

from pathlib import Path

from core.security.release_runtime_surface import is_runtime_release_excluded


def test_runtime_release_excludes_dev_only_and_volatile_artifacts(tmp_path: Path) -> None:
    included = tmp_path / 'runtime' / 'keep.py'
    included.parent.mkdir(parents=True, exist_ok=True)
    included.write_text('pass\n', encoding='utf-8')

    excluded = [
        'tests/test_sample.py',
        'docs/guide.md',
        'examples/demo.py',
        'scripts/tool.py',
        'ci/pipeline.yml',
        '.github/workflows/ci.yml',
        'data/runtime/state.sqlite3',
        'data/runtime/state.sqlite3-wal',
        '.pytest_cache/v/cache',
        'dist/release.zip',
    ]
    for rel in excluded:
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('x\n', encoding='utf-8')

    assert not is_runtime_release_excluded('runtime/keep.py', included)
    for rel in excluded:
        path = tmp_path / rel
        assert is_runtime_release_excluded(rel, path), rel
