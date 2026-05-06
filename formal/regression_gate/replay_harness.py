from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

from .differential import ContractDiff, compare_contracts
from .golden_trace import TraceDiff, compare_traces

Runner = Callable[[Mapping[str, Any]], Mapping[str, Any]]


@dataclass(frozen=True)
class ReplayCase:
    name: str
    payload: Mapping[str, Any]
    expected_contract: Mapping[str, Any]
    expected_trace: Mapping[str, Any]


@dataclass(frozen=True)
class ReplayResult:
    case_name: str
    observed_contract: Mapping[str, Any]
    observed_trace: Mapping[str, Any]
    contract_diff: ContractDiff
    trace_diff: TraceDiff

    @property
    def ok(self) -> bool:
        return self.contract_diff.equal and self.trace_diff.equal



def run_replay_case(case: ReplayCase, runner: Runner) -> ReplayResult:
    observed = dict(runner(case.payload))
    observed_trace = observed.get("trace", {})
    contract_diff = compare_contracts(case.expected_contract, observed)
    trace_diff = compare_traces(case.expected_trace, observed_trace)
    return ReplayResult(
        case_name=case.name,
        observed_contract=observed,
        observed_trace=observed_trace,
        contract_diff=contract_diff,
        trace_diff=trace_diff,
    )



def run_replay_suite(cases: Iterable[ReplayCase], runner: Runner) -> dict[str, Any]:
    results = [run_replay_case(case, runner) for case in cases]
    return {
        "checked_cases": len(results),
        "failing_cases": [
            {
                "case": result.case_name,
                "contract_diff": result.contract_diff.differing_keys,
                "trace_diff": result.trace_diff.differing_keys,
            }
            for result in results
            if not result.ok
        ],
        "ok": all(result.ok for result in results),
    }
