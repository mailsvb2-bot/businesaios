from __future__ import annotations

from scripts.ci.contracts import ExecutionReport
from scripts.ci.summary import write_failure_summary


def test_failure_summary_file_name_is_stable(tmp_path, monkeypatch) -> None:
    from scripts.ci import summary as summary_module

    monkeypatch.setattr(summary_module, "summaries_dir", lambda: tmp_path)

    report = ExecutionReport(gate="full", goal="goal")
    path = write_failure_summary(report)
    assert path.name == "full.failure-summary.txt"
