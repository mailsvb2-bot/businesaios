from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT / "runtime" / "handlers" / "ads_autopilot_flow.py"

BANNED_ARG_NAMES = {
    "payload",
    "data",
    "body",
    "request",
    "params",
    "envelope",
    "result",
    "response",
    "recommendation",
    "recommendations",
    "proposal",
    "proposals",
}


def test_execution_boundary_does_not_accept_payload_bridge_arguments() -> None:
    if not TARGET.exists():
        return

    tree = ast.parse(TARGET.read_text(encoding="utf-8"))
    offenders: dict[str, list[str]] = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if "execution" not in node.name:
            continue

        bad_args: list[str] = []

        for arg in node.args.args:
            if arg.arg in BANNED_ARG_NAMES:
                bad_args.append(arg.arg)

        if bad_args:
            offenders[node.name] = sorted(set(bad_args))

    assert not offenders, (
        "Execution boundary functions may not accept payload-like bridge arguments. "
        "They must require explicit DecisionCommand instead. "
        f"Offenders: {offenders}"
    )
