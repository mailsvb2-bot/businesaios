from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ALLOWED_TOP_LEVEL_CONFIG_FILES = {
    ".env.example",
    "pytest.ini",
    "ruff.toml",
    "mypy-world-model.ini",
}

ALLOWED_TOP_LEVEL_CONFIG_DIRS = {
    "config",
    "deploy",
    "products",
}


def test_top_level_config_surface_is_curated() -> None:
    violations: list[str] = []

    for path in ROOT.iterdir():
        if not path.is_file():
            continue
        name = path.name
        if name in ALLOWED_TOP_LEVEL_CONFIG_FILES:
            continue
        lowered = name.lower()
        if lowered.endswith((".env", ".env.sample", ".env.example", ".ini", ".toml", ".yaml", ".yml")):
            violations.append(name)

    assert violations == [], violations


def test_config_like_directories_live_in_curated_locations() -> None:
    violations: list[str] = []

    for path in ROOT.iterdir():
        if not path.is_dir():
            continue
        name = path.name
        lowered = name.lower()
        if lowered in ALLOWED_TOP_LEVEL_CONFIG_DIRS:
            continue
        if "config" in lowered:
            violations.append(name)

    assert violations == [], violations
