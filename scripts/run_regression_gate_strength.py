from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from formal.proof_obligations import try_prove_runtime_decision_gate, verify_runtime_decision_model
from formal.regression_gate import (
    evaluate_mutation_strength,
    replay_cases_from_corpus,
    run_project_snapshot_bundle,
    replay_runtime_decision,
    run_replay_suite,
)


def main() -> int:
    cases = replay_cases_from_corpus()
    replay = run_replay_suite(cases, replay_runtime_decision)
    mutation = evaluate_mutation_strength(cases, replay_runtime_decision)
    formal = verify_runtime_decision_model()
    smt = try_prove_runtime_decision_gate()
    formal_expectation_ok = formal["checked_cases"] == 32 and bool(formal["failing_cases"]) and formal["passing_cases"] < formal["checked_cases"]
    smt_expectation_ok = smt.get("ok") or smt.get("skipped", False)
    snapshot_bundle = run_project_snapshot_bundle()
    report = {
        "replay": replay,
        "mutation": mutation,
        "snapshot_bundle": snapshot_bundle,
        "formal": formal,
        "formal_expectation_ok": formal_expectation_ok,
        "smt": smt,
        "smt_expectation_ok": smt_expectation_ok,
        "ok": replay["ok"] and mutation["ok"] and snapshot_bundle["ok"] and formal_expectation_ok and smt_expectation_ok,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
