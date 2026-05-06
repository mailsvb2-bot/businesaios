from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class Violation:
    severity: str
    kind: str
    path: str
    line: int | None
    message: str
    hint: str | None = None


@dataclass(slots=True)
class EnforcerReport:
    ok: bool
    violations: list[Violation] = field(default_factory=list)

    def add(self, *, severity: str, kind: str, path: str, line: int | None, message: str, hint: str | None = None) -> None:
        self.violations.append(Violation(severity=severity, kind=kind, path=path, line=line, message=message, hint=hint))

    def recompute_ok(self) -> None:
        self.ok = not any(v.severity in {"critical", "high"} for v in self.violations)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "violations": [asdict(v) for v in self.violations]}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def render_text(self) -> str:
        if not self.violations:
            return "CANON ENFORCER: no violations found."
        lines = []
        for v in self.violations:
            where = f"{v.path}:{v.line}" if v.line else v.path
            hint = f" | hint: {v.hint}" if v.hint else ""
            lines.append(f"[{v.severity.upper()}] {v.kind} @ {where} -> {v.message}{hint}")
        return "\n".join(lines)
