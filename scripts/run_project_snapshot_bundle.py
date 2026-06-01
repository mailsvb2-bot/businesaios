from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from formal.regression_gate.project_snapshot_bundle import (
    run_project_snapshot_bundle,
    summarize_project_snapshot_bundle,
)


def main() -> int:
    summary = summarize_project_snapshot_bundle()
    report = run_project_snapshot_bundle()
    payload = {
        "summary": summary,
        "report": report,
        "ok": summary["ok"] and report["ok"],
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
