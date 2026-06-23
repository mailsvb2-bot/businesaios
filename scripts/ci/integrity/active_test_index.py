from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]

RISK_TERMS: dict[str, tuple[str, ...]] = {
    "P0_NO_SECOND_BRAIN": (
        "second_brain",
        "second-brain",
        "second brain",
        "no_second_brain",
        "anti_second_brain",
    ),
    "P0_SINGLE_DECISIONCORE": (
        "DecisionCore",
        "decisioncore",
        "single_decision_core",
        "single_decisioncore",
        "no_second_decision_core",
    ),
    "P0_SINGLE_PATH": (
        "single-path",
        "single path",
        "one execution contract",
        "single_entrypoint",
        "single entrypoint",
    ),
    "P0_ARCHITECTURE_BYPASS": (
        "architecture bypass",
        "architecture_bypass",
        "bypass scanner",
    ),
    "P0_RUNTIME_ACTIONS_REGISTRY": (
        "runtime actions registry",
        "runtime action",
        "actions_registry",
        "registration_manifest",
    ),
    "P0_DOCTOR_CONTRACT": (
        "doctor",
        "project shape",
        "workflow entrypoint",
        "empty ci files",
    ),
    "P1_ADMIN_SURFACE": (
        "admin",
        "control_plane",
        "control-plane",
        "approvals",
        "operator_override",
    ),
    "P1_EVIDENCE_REPLAY": (
        "evidence",
        "replay",
        "proof",
        "decision_ledger",
    ),
    "P1_CANONICAL_FLOW": (
        "signal",
        "state",
        "decision",
        "policy",
        "guard",
        "execution",
        "verification",
        "archive",
    ),
}

GATES_TO_INDEX = (
    "doctor",
    "fast",
    "full",
    "business-critical",
    "targeted-domain",
    "integrity",
    "test-quality",
    "all-tests",
)


@dataclass(frozen=True)
class ActiveRiskCoverage:
    risk_id: str
    test_files_found: list[str]
    active_gates: list[str]
    active_steps: list[str]
    status: str


@dataclass(frozen=True)
class TestInventory:
    total_test_files: int
    all_tests_gate_present: bool
    pytest_root: str


@dataclass(frozen=True)
class ActiveTestIndex:
    risks: list[ActiveRiskCoverage]
    inventory: TestInventory

    def to_json(self) -> dict[str, Any]:
        return {
            "inventory": asdict(self.inventory),
            "risks": [asdict(item) for item in self.risks],
        }


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def _all_test_files() -> list[str]:
    tests_root = ROOT / "tests"
    if not tests_root.exists():
        return []
    return sorted(path.relative_to(ROOT).as_posix() for path in tests_root.rglob("*.py"))


def _test_files_for_terms(terms: tuple[str, ...]) -> list[str]:
    tests_root = ROOT / "tests"
    if not tests_root.exists():
        return []
    found: list[str] = []
    for path in sorted(tests_root.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        blob = f"{rel}\n{_read(path)}"
        if _contains_any(blob, terms):
            found.append(rel)
    return found


def _step_file_for(step_name: str) -> Path:
    return ROOT / "scripts" / "ci" / f"step_{step_name.replace('-', '_')}.py"


def _gate_plan_steps() -> dict[str, tuple[str, ...]]:
    from scripts.ci.plan_registry import plan_for_gate

    out: dict[str, tuple[str, ...]] = {}
    for gate in GATES_TO_INDEX:
        try:
            plan = plan_for_gate(gate)
        except Exception:
            continue

        steps = getattr(plan, "steps", ())
        names: list[str] = []
        for step in steps:
            if isinstance(step, str):
                names.append(step)
            else:
                names.append(str(getattr(step, "name", step)))
        out[gate] = tuple(names)
    return out


def _active_refs_for_terms(terms: tuple[str, ...]) -> tuple[list[str], list[str]]:
    gates: list[str] = []
    steps_seen: set[str] = set()
    gate_steps = _gate_plan_steps()

    for gate, steps in gate_steps.items():
        gate_active = False
        for step in steps:
            step_path = _step_file_for(step)
            blob = f"{step}\n{_read(step_path)}"
            if _contains_any(blob, terms):
                gate_active = True
                steps_seen.add(step)
        if gate_active:
            gates.append(gate)

    return sorted(gates), sorted(steps_seen)


def build_active_test_index() -> ActiveTestIndex:
    risks: list[ActiveRiskCoverage] = []

    for risk_id, terms in RISK_TERMS.items():
        tests = _test_files_for_terms(terms)
        gates, steps = _active_refs_for_terms(terms)

        if tests and gates:
            status = "active"
        elif tests and not gates:
            status = "tests_found_but_no_active_gate_detected"
        elif not tests and gates:
            status = "gate_detected_but_no_test_files_found"
        else:
            status = "missing"

        risks.append(
            ActiveRiskCoverage(
                risk_id=risk_id,
                test_files_found=tests,
                active_gates=gates,
                active_steps=steps,
                status=status,
            )
        )

    gate_steps = _gate_plan_steps()
    inventory = TestInventory(
        total_test_files=len(_all_test_files()),
        all_tests_gate_present="all-tests" in gate_steps and "all-tests" in gate_steps.get("all-tests", ()),
        pytest_root="tests",
    )
    return ActiveTestIndex(risks=risks, inventory=inventory)
