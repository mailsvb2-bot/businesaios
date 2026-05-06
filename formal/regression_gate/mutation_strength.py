from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

from .differential import compare_contracts
from .golden_trace import compare_traces
from .replay_harness import ReplayCase

Mutator = Callable[[ReplayCase], ReplayCase]


@dataclass(frozen=True)
class MutationProbeResult:
    mutator_name: str
    killed: bool
    details: str



def mutate_contract_status(case: ReplayCase) -> ReplayCase:
    mutated = dict(case.expected_contract)
    mutated["status"] = "executed" if mutated.get("status") == "blocked" else "blocked"
    return ReplayCase(case.name, case.payload, mutated, case.expected_trace)



def mutate_trace_route(case: ReplayCase) -> ReplayCase:
    mutated_trace = dict(case.expected_trace)
    mutated_trace["route"] = "Mutated->Bypass"
    return ReplayCase(case.name, case.payload, case.expected_contract, mutated_trace)



def mutate_trace_guard(case: ReplayCase) -> ReplayCase:
    mutated_trace = dict(case.expected_trace)
    mutated_trace["guard_passed"] = not bool(mutated_trace.get("guard_passed", False))
    return ReplayCase(case.name, case.payload, case.expected_contract, mutated_trace)


DEFAULT_MUTATORS: tuple[tuple[str, Mutator], ...] = (
    ("contract_status_flip", mutate_contract_status),
    ("trace_route_bypass", mutate_trace_route),
    ("trace_guard_flip", mutate_trace_guard),
)



def evaluate_mutation_strength(cases: Iterable[ReplayCase], runner: Callable[[Mapping[str, Any]], Mapping[str, Any]]) -> dict[str, Any]:
    probes: list[MutationProbeResult] = []
    materialized = list(cases)
    for name, mutator in DEFAULT_MUTATORS:
        killed = False
        failure_details: list[str] = []
        for case in materialized:
            mutated = mutator(case)
            observed = dict(runner(mutated.payload))
            contract_diff = compare_contracts(mutated.expected_contract, observed)
            trace_diff = compare_traces(mutated.expected_trace, observed.get("trace", {}))
            if not contract_diff.equal or not trace_diff.equal:
                killed = True
            else:
                failure_details.append(mutated.name)
        probes.append(
            MutationProbeResult(
                mutator_name=name,
                killed=killed,
                details="all killed" if killed else f"survived cases: {', '.join(failure_details)}",
            )
        )
    killed = sum(1 for probe in probes if probe.killed)
    total = len(probes)
    return {
        "mutation_score": killed / total if total else 0.0,
        "killed": killed,
        "total": total,
        "results": [probe.__dict__ for probe in probes],
        "ok": killed == total,
    }
