from __future__ import annotations

from pathlib import Path

import pytest

from runtime.bootstrap.entrypoint_manifest import (
    LEGACY_BOOTSTRAP_ENTRYPOINTS,
    canonical_bootstrap_surface_manifest,
)
from runtime.bootstrap.environment_loader import load_bootstrap_environment
from runtime.bootstrap.startup_validator import validate_single_bootstrap_path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _python_files() -> list[Path]:
    return [
        path
        for path in REPO_ROOT.rglob("*.py")
        if ".venv" not in path.parts and "__pycache__" not in path.parts
    ]


def _import_statement_hits(module_name: str) -> list[Path]:
    hits: list[Path] = []
    from_stmt = f"from {module_name} import"
    import_stmt = f"import {module_name}"
    for path in _python_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if from_stmt in text or import_stmt in text:
            hits.append(path.relative_to(REPO_ROOT))
    return hits


def test_no_repo_code_imports_legacy_bootstrap_public_surfaces_outside_boot_package() -> None:
    offenders: list[str] = []
    allowed_prefixes = ("boot/", "tests/")
    for module_name in LEGACY_BOOTSTRAP_ENTRYPOINTS:
        for hit in _import_statement_hits(module_name):
            normalized = hit.as_posix()
            if normalized.startswith(allowed_prefixes):
                continue
            offenders.append(f"{module_name} <- {normalized}")

    assert offenders == []


@pytest.mark.parametrize(
    "legacy_module",
    [
        "boot.bootstrap",
        "boot.app_public_api",
        "boot.http_public_api",
        "boot.public_api",
        "boot.runtime_public_api",
        "boot.facade",
    ],
)
def test_startup_validator_rejects_all_legacy_bootstrap_surfaces(
    tmp_path, monkeypatch, legacy_module: str
) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    env = load_bootstrap_environment(project_root=tmp_path)

    with pytest.raises(RuntimeError) as exc:
        validate_single_bootstrap_path(
            loaded_modules={
                "runtime.bootstrap.sovereign_bootstrap",
                legacy_module,
            },
            env=env,
        )

    assert "LEGACY_BOOTSTRAP_ENTRYPOINT_DETECTED" in str(exc.value)


def test_bootstrap_surface_manifest_keeps_single_public_owner() -> None:
    manifest = canonical_bootstrap_surface_manifest()
    assert manifest.sovereign_public_modules == (
        "runtime.bootstrap",
        "runtime.bootstrap.sovereign_bootstrap",
    )
