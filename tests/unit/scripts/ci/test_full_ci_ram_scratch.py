from pathlib import Path

WORKFLOW = Path(".github/workflows/full-ci.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_literal_pytest_uses_ram_backed_isolated_scratch() -> None:
    text = _workflow_text()
    assert "BAIOS_LITERAL_PYTEST_TMP: /dev/shm/businesaios-pytest/" in text
    assert 'export TMPDIR="$scratch" TMP="$scratch" TEMP="$scratch"' in text
    assert '--basetemp="$scratch/pytest"' in text


def test_literal_pytest_scratch_is_guarded_and_cleaned() -> None:
    text = _workflow_text()
    assert '/dev/shm/businesaios-pytest/*) ;;' in text
    assert 'refusing unsafe pytest scratch path' in text
    assert "trap 'rm -rf -- \"$BAIOS_LITERAL_PYTEST_TMP\"' EXIT" in text
