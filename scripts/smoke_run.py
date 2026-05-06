from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ci.subprocess_io import run_command


def _run(label: str, env_patch: dict[str, str], argv: list[str]) -> int:
    env = os.environ.copy()
    temp_root = Path(tempfile.mkdtemp(prefix=f"businesaios_smoke_{label}_"))
    data_dir = temp_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    env.update({
        "PYTHONDONTWRITEBYTECODE": "1",
        "DATA_DIR": str(data_dir),
        "APP_DATA_DIR": str(data_dir),
        "RUNTIME_DATA_DIR": str(data_dir),
    })
    env.update(env_patch)
    try:
        outcome = run_command(
            argv,
            cwd=ROOT,
            env=env,
            timeout=120,
        )
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
    sys.stdout.write(f"===== {label} =====\n")
    if outcome.stdout:
        sys.stdout.write(outcome.stdout[-4000:])
        if not outcome.stdout.endswith("\n"):
            sys.stdout.write("\n")
    if outcome.stderr:
        sys.stdout.write(outcome.stderr[-4000:])
        if not outcome.stderr.endswith("\n"):
            sys.stdout.write("\n")
    sys.stdout.write(f"[{label}] exit_code={outcome.returncode}\n")
    return int(outcome.returncode)


def main() -> int:
    demo_code = _run(
        "demo",
        {"RUN_MODE": "demo", "APP_ENV": "dev", "ENV": "dev"},
        [sys.executable, "main.py"],
    )
    evo_code = _run(
        "evolution",
        {
            "RUN_MODE": "evolution",
            "APP_ENV": "dev",
            "ENV": "dev",
            "EVOLUTION_MAX_RUNTIME_SEC": "1",
            "EVOLUTION_TICK_SEC": "1",
        },
        [sys.executable, "-m", "runtime.evolution.main"],
    )
    if demo_code or evo_code:
        return 1
    print("[ok] smoke run passed for demo and evolution entrypoints")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
