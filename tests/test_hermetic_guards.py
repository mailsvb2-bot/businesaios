from __future__ import annotations

from pathlib import Path


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_pytest_ini_disables_cache_and_ddtrace():
    root = Path(__file__).resolve().parents[1]
    ini = root / "pytest.ini"
    assert ini.exists(), "pytest.ini missing (required for hermetic runs)"
    txt = _read(ini)
    # Ensure we don't create .pytest_cache and we don't load ddtrace pytest plugin.
    assert "-p no:cacheprovider" in txt, "pytest.ini must disable cacheprovider"
    assert "-p no:ddtrace" in txt, "pytest.ini must disable ddtrace pytest plugin"


def test_sitecustomize_sets_hermetic_env_barriers():
    root = Path(__file__).resolve().parents[1]
    sc = root / "sitecustomize.py"
    assert sc.exists(), "sitecustomize.py missing (required to keep repo clean)"
    txt = _read(sc)

    assert "sys.dont_write_bytecode" in txt, "sitecustomize must disable bytecode writing"
    assert "PYTEST_DISABLE_PLUGIN_AUTOLOAD" in txt, "sitecustomize must disable external pytest plugins"
    assert "DD_TRACE_ENABLED" in txt, "sitecustomize must disable ddtrace auto-instrumentation"


def test_hermetic_test_runner_exists_and_sets_barriers():
    root = Path(__file__).resolve().parents[1]
    runner = root / "scripts" / "run_tests_clean.py"
    assert runner.exists(), "scripts/run_tests_clean.py missing"
    txt = _read(runner)

    # Runner must set env barriers BEFORE importing pytest.
    assert "PYTEST_DISABLE_PLUGIN_AUTOLOAD" in txt
    assert "DD_TRACE_ENABLED" in txt
    assert "PYTHONDONTWRITEBYTECODE" in txt

    # Sanity: ensure pytest is imported after env is set
    env_pos = txt.find("PYTEST_DISABLE_PLUGIN_AUTOLOAD")
    pytest_pos = txt.find("import pytest")
    assert env_pos != -1 and pytest_pos != -1 and env_pos < pytest_pos, (
        "run_tests_clean.py must set env barriers before importing pytest"
    )


def test_clean_script_present():
    root = Path(__file__).resolve().parents[1]
    clean = root / "scripts" / "clean_artifacts.sh"
    assert clean.exists(), "scripts/clean_artifacts.sh missing"
