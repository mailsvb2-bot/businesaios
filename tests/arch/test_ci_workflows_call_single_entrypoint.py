from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_ROOT = ROOT / ".github" / "workflows"
CANONICAL_CLI_ENTRYPOINT = "python -m scripts.ci.cli --gate"
LEGACY_CLI_FILE_ENTRYPOINT = "scripts/ci/cli.py"


def _gate_workflows() -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(WORKFLOW_ROOT.glob("*.yml"))
        if "scripts.ci.cli" in path.read_text(encoding="utf-8")
    )


def test_workflows_use_single_cli_entrypoint() -> None:
    workflows = _gate_workflows()
    assert workflows, "at least one canonical gate workflow is required"

    offenders: list[str] = []
    for path in workflows:
        text = path.read_text(encoding="utf-8")
        if CANONICAL_CLI_ENTRYPOINT not in text or LEGACY_CLI_FILE_ENTRYPOINT in text:
            offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders, f"workflow does not use canonical entrypoint: {offenders}"
