from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RuntimeManifestEntry:
    step_name: str
    module_path: str
    callable_name: str
    service_name: str
    service_type: str
    dependencies: tuple[str, ...] = field(default_factory=tuple)
