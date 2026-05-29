from __future__ import annotations

from pathlib import Path

from interfaces.api.fastapi_app_factory import create_fastapi_app


def test_fastapi_app_factory_reads_version_from_project_root(monkeypatch, tmp_path: Path) -> None:
    external = tmp_path / 'external'
    external.mkdir()
    (external / 'VERSION').write_text('999.999.999\n', encoding='utf-8')
    monkeypatch.chdir(external)
    app = create_fastapi_app(application_service=object())
    expected = (Path(__file__).resolve().parents[2] / 'VERSION').read_text(encoding='utf-8').strip()
    assert app.version == expected
