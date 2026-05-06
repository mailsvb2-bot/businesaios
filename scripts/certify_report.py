from __future__ import annotations

from dataclasses import dataclass, field

TRUTHY = {"1", "true", "TRUE", "yes", "YES", "on", "ON"}


@dataclass
class CertificationReport:
    violations: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)

    @property
    def errors(self) -> list[str]:
        return self.violations

    @property
    def ok(self) -> bool:
        return not self.violations

    def add_error(self, message: str) -> None:
        self.violations.append(str(message))

    def add_warning(self, message: str) -> None:
        self.warnings.append(str(message))

    def render_text(self) -> str:
        lines: list[str] = []
        lines += [f"ERROR: {x}" for x in self.violations]
        lines += [f"WARN: {x}" for x in self.warnings]
        lines += [f"SIGNAL: {x}" for x in self.signals]
        return "\n".join(lines or ["OK"])

    def render(self) -> str:
        return self.render_text()
