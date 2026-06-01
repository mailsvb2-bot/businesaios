from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from canon.domain_fs import (
    findings_as_dicts,
    scan_boot_wiring_only,
    scan_canon_domain_file_system,
    scan_thin_runtime_handlers,
)


def main() -> int:
    root = ROOT
    findings=[]
    findings.extend(scan_canon_domain_file_system(root))
    findings.extend(scan_thin_runtime_handlers(root))
    findings.extend(scan_boot_wiring_only(root))
    if findings:
        print(json.dumps(findings_as_dicts(findings), ensure_ascii=False, indent=2))
        return 1
    print("Canon domain file-system checks passed.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
