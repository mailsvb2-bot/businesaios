from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    config = repo_root / "mypy-world-model.ini"
    targets = [
        "runtime/boot/world_model_contract.py",
        "runtime/boot/canonical_decision_world_model.py",
        "runtime/boot/world_model_builder.py",
        "runtime/boot/world_model_boot_check.py",
        "runtime/boot/world_model_self_check.py",
        "runtime/boot/world_model_forbidden_paths.py",
        "application/decision_state/world_model_metadata.py",
        "kernel/world_model_pin.py",
        "application/decision_state/world_model_replay.py",
        "runtime/enforcement/world_model_pin_guard.py",
        "runtime/events/world_model_events.py",
    ]
    try:
        from mypy import api as mypy_api
    except Exception:
        sys.stderr.write("mypy is not installed\n")
        return 2

    argv = ["--config-file", str(config), *targets]
    stdout, stderr, exit_status = mypy_api.run(argv)
    if stdout:
        sys.stdout.write(stdout)
    if stderr:
        sys.stderr.write(stderr)
    return int(exit_status)


if __name__ == "__main__":
    raise SystemExit(main())
