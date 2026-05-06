from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple


@dataclass(frozen=True)
class ArchitectureViolation:
    code: str
    message: str
    subject: str
    severity: str = "error"


@dataclass(frozen=True)
class HardGateResult:
    gate_name: str
    passed: bool
    message: str


@dataclass(frozen=True)
class SymbolRef:
    module: str
    export_name: str
    canonical_key: str
    file_path: Optional[Path] = None
    lineno: Optional[int] = None

    @property
    def fqname(self) -> str:
        return f"{self.module}:{self.export_name}"


@dataclass(frozen=True)
class ArchitectureReport:
    raw_score_100: float
    admission_score_100: float
    violations: Tuple[ArchitectureViolation, ...]
    hard_gates: Tuple[HardGateResult, ...]
    passed: bool
