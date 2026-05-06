from __future__ import annotations

import json
from pathlib import Path

from runtime.platform.support.cli._main_stub import cli_main
from runtime.platform.support.data.dataset_writer import DatasetWriter
from runtime.platform.support.contracts.action import Action
from runtime.platform.support.contracts.observation import Observation
from runtime.platform.support.contracts.reward import Reward
from runtime.platform.support.contracts.trajectory import Trajectory
from runtime.platform.support.contracts.transition import Transition


def test_cli_main_datasets_reads_local_dataset(tmp_path, capsys, monkeypatch) -> None:
    dataset_path = tmp_path / "datasets.jsonl"
    DatasetWriter().write(
        str(dataset_path),
        [
            Trajectory(
                transitions=(
                    Transition(
                        observation=Observation(data={"lead": 1}),
                        action=Action(name="route", payload={"target": "sales"}),
                        reward=Reward(value=1.5),
                        done=True,
                    ),
                )
            )
        ],
    )
    monkeypatch.setenv("BUSINESAIOS_PLATFORM_SUPPORT_DIR", str(tmp_path / "workspace"))
    assert cli_main("datasets", argv=(str(dataset_path),)) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "datasets"
    assert payload["trajectory_count"] == 1
    assert payload["transition_count"] == 1


def test_cli_main_train_persists_local_job_record(tmp_path, capsys, monkeypatch) -> None:
    monkeypatch.setenv("BUSINESAIOS_PLATFORM_SUPPORT_DIR", str(tmp_path / "workspace"))
    assert cli_main("train", argv=("--model", "baseline")) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "train"
    job_path = Path(payload["path"])
    assert job_path.exists()
    row = json.loads(job_path.read_text(encoding="utf-8").splitlines()[0])
    assert row["command"] == "train"
    assert row["argv"] == ["--model", "baseline"]


def test_cli_main_inspect_reports_workspace_state(tmp_path, capsys, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "datasets").mkdir(parents=True)
    (workspace / "datasets" / "sample.jsonl").write_text("", encoding="utf-8")
    monkeypatch.setenv("BUSINESAIOS_PLATFORM_SUPPORT_DIR", str(workspace))
    assert cli_main("inspect", argv=()) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["command"] == "inspect"
    assert payload["datasets"] == ["sample.jsonl"]
