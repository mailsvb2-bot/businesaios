from __future__ import annotations

from pathlib import Path


def test_package_roots_no_longer_install_alias_modules() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    offenders: list[str] = []
    for path in repo_root.rglob('__init__.py'):
        rel = path.relative_to(repo_root).as_posix()
        if rel.startswith('tests/') or rel.startswith('shared/'):
            continue
        text = path.read_text(encoding='utf-8')
        if 'install_alias_modules(' in text or 'register_alias_modules(' in text or 'install_package_submodule_alias(' in text:
            offenders.append(rel)
    assert offenders == []
