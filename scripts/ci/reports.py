from __future__ import annotations

import json
from pathlib import Path

from scripts.ci.contracts import ExecutionReport
from scripts.ci.fs import safe_write_text


def write_report(path: Path, report: ExecutionReport) -> None:
    safe_write_text(
        path,
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
