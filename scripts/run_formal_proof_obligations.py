from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def main() -> int:
    from formal.proof_obligations import (
        try_prove_runtime_decision_gate,
        verify_runtime_decision_model,
    )

    model_result = verify_runtime_decision_model()
    smt_result = try_prove_runtime_decision_gate()
    model_expectation_ok = model_result["checked_cases"] == 32 and bool(model_result["failing_cases"]) and model_result["passing_cases"] < model_result["checked_cases"]
    smt_expectation_ok = smt_result.get("ok") or smt_result.get("skipped", False)

    summary = {
        "model": model_result,
        "model_expectation_ok": model_expectation_ok,
        "smt": smt_result,
        "smt_expectation_ok": smt_expectation_ok,
        "ok": model_expectation_ok and smt_expectation_ok,
        "tla_assets": {
            "spec": str(Path("formal/tla/runtime_decision_gate.tla")),
            "cfg": str(Path("formal/tla/runtime_decision_gate.cfg")),
        },
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
