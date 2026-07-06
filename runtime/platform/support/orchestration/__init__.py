"""Canonical orchestration surface with compat alias submodules."""

from __future__ import annotations

from dataclasses import dataclass


class ConcurrencyLimits:
    def allows(self, current: int, maximum: int) -> bool:
        return current < maximum

class JobDispatcher:
    def dispatch(self, jobs):
        return list(jobs)

class JobRecovery:
    def recover(self, job_name: str) -> dict[str, str]:
        return {"job": job_name, "recovered": "true"}

class JobRunner:
    def run(self, job):
        return job()

@dataclass(frozen=True)
class JobSpec:
    name: str
    priority: int = 0

class Leases:
    def acquire(self, resource: str) -> dict[str, str]:
        return {"resource": resource, "leased": "true"}

@dataclass(frozen=True)
class PriorityClass:
    name: str
    value: int

class Quotas:
    def within(self, used: int, limit: int) -> bool:
        return used <= limit

class TaskGraph:
    def __init__(self) -> None:
        self._edges: dict[str, list[str]] = {}

    def add_edge(self, left: str, right: str) -> None:
        self._edges.setdefault(left, []).append(right)

    def edges(self) -> dict[str, list[str]]:
        return {key: list(value) for key, value in self._edges.items()}

class DAGBuilder:
    def build(self, edges: list[tuple[str, str]]) -> TaskGraph:
        graph = TaskGraph()
        for left, right in edges:
            graph.add_edge(left, right)
        return graph

class WorkflowEvents:
    def started(self, workflow_name: str) -> dict[str, str]:
        return {"event": "started", "workflow": workflow_name}

    def finished(self, workflow_name: str) -> dict[str, str]:
        return {"event": "finished", "workflow": workflow_name}

class WorkflowGC:
    def collect(self, states: list[dict]) -> list[dict]:
        return [state for state in states if not state.get("finished", False)]

class WorkflowRecovery:
    def recover(self, workflow_name: str) -> dict[str, str]:
        return {"workflow": workflow_name, "recovered": "true"}

class WorkflowRegistry:
    def __init__(self) -> None:
        self._workflows: dict[str, object] = {}

    def register(self, name: str, workflow: object) -> None:
        self._workflows[name] = workflow

    def get(self, name: str) -> object:
        return self._workflows[name]

class WorkflowRetry:
    def should_retry(self, attempts: int, max_attempts: int) -> bool:
        return attempts < max_attempts

class WorkflowRunner:
    def run(self, steps):
        result = None
        for step in steps:
            result = step()
        return result

@dataclass
class WorkflowState:
    step: int = 0

_ALIAS_EXPORTS = {
    "concurrency_limits": "ConcurrencyLimits",
    "dag_builder": "DAGBuilder",
    "job_dispatcher": "JobDispatcher",
    "job_recovery": "JobRecovery",
    "job_runner": "JobRunner",
    "job_spec": "JobSpec",
    "leases": "Leases",
    "priority_classes": "PriorityClass",
    "quotas": "Quotas",
    "task_graph": "TaskGraph",
    "workflow_events": "WorkflowEvents",
    "workflow_gc": "WorkflowGC",
    "workflow_recovery": "WorkflowRecovery",
    "workflow_registry": "WorkflowRegistry",
    "workflow_retry": "WorkflowRetry",
    "workflow_runner": "WorkflowRunner",
    "workflow_state": "WorkflowState",
}

__all__ = [
    "ConcurrencyLimits",
    "DAGBuilder",
    "JobDispatcher",
    "JobRecovery",
    "JobRunner",
    "JobSpec",
    "Leases",
    "PriorityClass",
    "Quotas",
    "TaskGraph",
    "WorkflowEvents",
    "WorkflowGC",
    "WorkflowRecovery",
    "WorkflowRegistry",
    "WorkflowRetry",
    "WorkflowRunner",
    "WorkflowState",
] + list(_ALIAS_EXPORTS)
