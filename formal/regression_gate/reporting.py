from __future__ import annotations

from .differential import ContractDiff
from .golden_trace import TraceDiff


def render_contract_diff_report(diff: ContractDiff) -> str:
    if diff.equal:
        return "contract-equivalent"
    return "contract-diff: " + ", ".join(diff.differing_keys)


def render_trace_diff_report(diff: TraceDiff) -> str:
    if diff.equal:
        return "trace-equivalent"
    return "trace-diff: " + ", ".join(diff.differing_keys)
