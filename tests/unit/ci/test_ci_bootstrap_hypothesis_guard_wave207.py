from __future__ import annotations

from dataclasses import dataclass

from scripts.ci import bootstrap


@dataclass
class Outcome:
    returncode: int = 0


def test_ci_bootstrap_verifies_hypothesis_import(monkeypatch, tmp_path) -> None:
    calls: list[list[str]] = []

    monkeypatch.setattr(bootstrap, 'repo_root', lambda: tmp_path)
    (tmp_path / 'requirements.txt').write_text('hypothesis==6.92.1\n', encoding='utf-8')
    (tmp_path / 'requirements.optional.txt').write_text('', encoding='utf-8')

    def fake_run_python(args):
        calls.append(list(args))
        return Outcome(0)

    monkeypatch.setattr(bootstrap, 'run_python', fake_run_python)

    assert bootstrap.main() == 0
    assert ['-c', 'import hypothesis'] in calls
