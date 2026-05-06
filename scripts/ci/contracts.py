from __future__ import annotations

from dataclasses import asdict, dataclass, field


GateName = str
StepName = str
StepStatus = str


@dataclass(frozen=True)
class ExecutionRequest:
    gate: GateName
    emit_report: bool = True
    emit_junit: bool = True
    emit_coverage: bool = True


@dataclass(frozen=True)
class StepDefinition:
    name: StepName
    required: bool = True


@dataclass(frozen=True)
class StepResult:
    name: StepName
    status: StepStatus
    message: str
    duration_ms: int


@dataclass(frozen=True)
class ExecutionPlan:
    gate: GateName
    steps: tuple[StepDefinition, ...]


@dataclass
class ExecutionReport:
    gate: GateName
    goal: str
    steps: list[StepResult] = field(default_factory=list)

    def add(self, result: StepResult) -> None:
        self.steps.append(result)

    @property
    def success(self) -> bool:
        return all(step.status != "failed" for step in self.steps)

    def to_dict(self) -> dict:
        return {
            "gate": self.gate,
            "goal": self.goal,
            "success": self.success,
            "steps": [asdict(step) for step in self.steps],
        }
