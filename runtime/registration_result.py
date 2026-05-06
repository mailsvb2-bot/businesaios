from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RegistrationResult:
    service_name: str
    service_type: str
    implementation_type: str
    dependencies: tuple[str, ...] = field(default_factory=tuple)
