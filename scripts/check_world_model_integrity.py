from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def main() -> int:
    from bootstrap.world_model_forbidden_paths import scan_repo_for_forbidden_world_model_paths

    findings = scan_repo_for_forbidden_world_model_paths(repo_root=REPO_ROOT)

    payload = {
        "ok": not findings,
        "repo_root": str(REPO_ROOT),
        "findings_count": len(findings),
        "findings": findings,
    }

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
