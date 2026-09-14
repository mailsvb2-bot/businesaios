from pathlib import Path

WORKFLOW = Path(".github/workflows/full-ci.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_literal_pytest_uses_bounded_disk_scratch_not_tmpfs() -> None:
    text = _workflow_text()
    assert "BAIOS_LITERAL_PYTEST_TMP: ${{ runner.temp }}/businesaios-literal-pytest/" in text
    assert 'export TMPDIR="$scratch/tmp" TMP="$scratch/tmp" TEMP="$scratch/tmp"' in text
    assert '--basetemp="$scratch/pytest"' in text
    assert "BAIOS_LITERAL_PYTEST_TMP: /dev/shm/" not in text


def test_literal_pytest_releases_successful_tmp_path_directories_during_the_run() -> None:
    text = _workflow_text()
    assert "-o tmp_path_retention_policy=failed" in text
    assert 'find "/tmp/pytest-of-$(id -un)" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +' in text


def test_literal_pytest_scratch_is_guarded_and_cleaned() -> None:
    text = _workflow_text()
    assert '"${RUNNER_TEMP}"/businesaios-literal-pytest/*) ;;' in text
    assert 'refusing unsafe pytest scratch path' in text
    assert 'trap \'rm -rf -- "$BAIOS_LITERAL_PYTEST_TMP"\' EXIT' in text


def test_dependency_install_does_not_accumulate_runner_pip_cache() -> None:
    text = _workflow_text()
    assert 'PIP_NO_CACHE_DIR: "1"' in text
