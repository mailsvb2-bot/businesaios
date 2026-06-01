from __future__ import annotations

"""Small concrete implementations for platform-support CLI commands.

These commands intentionally stay local and explicit. They provide a usable
operator surface for offline tooling instead of decorative no-op entrypoints.
"""

import json
import os
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from runtime.platform.support.cli.registry import CLI_COMMANDS
from runtime.platform.support.cli.workspace import support_workspace_root, workspace_path
from runtime.platform.support.command_audit import _audit_path
from runtime.platform.support.data.dataset_loader import DatasetLoader

CommandImpl = Callable[[], int]


def build_cli_implementations(argv: Sequence[str] | None = None) -> dict[str, CommandImpl]:
    args = tuple(str(item) for item in (argv or ()))
    return {
        "audit": lambda: _audit(args),
        "checkpoints": lambda: _checkpoints(args),
        "datasets": lambda: _datasets(args),
        "evaluate": lambda: _evaluate(args),
        "experiments": lambda: _experiments(args),
        "governance": lambda: _governance(args),
        "inspect": lambda: _inspect(args),
        "lineage": lambda: _lineage(args),
        "main": lambda: _main(args),
        "promote": lambda: _promote(args),
        "rollback": lambda: _rollback(args),
        "rollout": lambda: _rollout(args),
        "train": lambda: _train(args),
    }


def _stdout(payload: Any) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _list_files(path: Path) -> list[str]:
    if not path.exists() or not path.is_dir():
        return []
    return sorted(item.name for item in path.iterdir())


def _main(args: Sequence[str]) -> int:
    _stdout(
        {
            "command": "main",
            "workspace": str(support_workspace_root()),
            "commands": list(CLI_COMMANDS),
            "argv": list(args),
        }
    )
    return 0


def _datasets(args: Sequence[str]) -> int:
    selected = str(args[0]).strip() if args else str(os.getenv("BUSINESAIOS_DATASET_PATH", "")).strip()
    if selected:
        trajectories = tuple(DatasetLoader().load(selected))
        transitions = sum(len(item.transitions) for item in trajectories)
        _stdout(
            {
                "command": "datasets",
                "dataset_path": selected,
                "trajectory_count": len(trajectories),
                "transition_count": transitions,
            }
        )
        return 0
    datasets_dir = workspace_path("datasets")
    _stdout(
        {
            "command": "datasets",
            "dataset_dir": str(datasets_dir),
            "files": _list_files(datasets_dir),
        }
    )
    return 0


def _experiments(args: Sequence[str]) -> int:
    path = workspace_path("experiments", "records.jsonl")
    records = []
    if path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if raw:
                records.append(json.loads(raw))
    _stdout(
        {
            "command": "experiments",
            "record_count": len(records),
            "path": str(path),
            "argv": list(args),
        }
    )
    return 0


def _checkpoints(args: Sequence[str]) -> int:
    path = workspace_path("checkpoints")
    _stdout(
        {
            "command": "checkpoints",
            "path": str(path),
            "files": _list_files(path),
            "argv": list(args),
        }
    )
    return 0


def _lineage(args: Sequence[str]) -> int:
    path = workspace_path("lineage")
    _stdout(
        {
            "command": "lineage",
            "path": str(path),
            "files": _list_files(path),
            "argv": list(args),
        }
    )
    return 0


def _audit(args: Sequence[str]) -> int:
    path = _audit_path()
    records = []
    if path is not None and path.exists():
        for raw in path.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if raw:
                records.append(json.loads(raw))
    _stdout(
        {
            "command": "audit",
            "audit_path": str(path) if path is not None else None,
            "record_count": len(records),
            "argv": list(args),
        }
    )
    return 0


def _inspect(args: Sequence[str]) -> int:
    root = support_workspace_root()
    payload = {
        "command": "inspect",
        "workspace": str(root),
        "datasets": _list_files(root / "datasets"),
        "checkpoints": _list_files(root / "checkpoints"),
        "lineage": _list_files(root / "lineage"),
        "argv": list(args),
    }
    _stdout(payload)
    return 0


def _append_job_record(name: str, args: Sequence[str], action: str | None = None) -> Path:
    path = workspace_path("jobs", f"{name}.jsonl")
    entry: dict[str, object] = {"command": name, "argv": list(args)}
    if action is not None:
        entry["action"] = action
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    return path


def _train(args: Sequence[str]) -> int:
    path = _append_job_record("train", args)
    _stdout({"command": "train", "queued": True, "path": str(path), "argv": list(args)})
    return 0


def _evaluate(args: Sequence[str]) -> int:
    path = _append_job_record("evaluate", args)
    _stdout({"command": "evaluate", "queued": True, "path": str(path), "argv": list(args)})
    return 0


def _rollout(args: Sequence[str]) -> int:
    path = _append_job_record("rollout", args, action="apply")
    _stdout({"command": "rollout", "queued": True, "path": str(path), "argv": list(args)})
    return 0


def _rollback(args: Sequence[str]) -> int:
    path = _append_job_record("rollback", args, action="revert")
    _stdout({"command": "rollback", "queued": True, "path": str(path), "argv": list(args)})
    return 0


def _promote(args: Sequence[str]) -> int:
    path = _append_job_record("promote", args, action="promote")
    _stdout({"command": "promote", "queued": True, "path": str(path), "argv": list(args)})
    return 0


def _governance(args: Sequence[str]) -> int:
    policy_path = workspace_path("governance", "policy.json")
    payload: dict[str, object] = {
        "command": "governance",
        "policy_path": str(policy_path),
        "exists": policy_path.exists(),
        "argv": list(args),
    }
    if policy_path.exists():
        payload["policy"] = json.loads(policy_path.read_text(encoding="utf-8"))
    _stdout(payload)
    return 0


__all__ = ["build_cli_implementations"]
