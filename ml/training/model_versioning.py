from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class ModelVersioning:
    versions: Dict[str, str] = field(default_factory=dict)

    def set(self, model_name: str, version: str) -> None:
        normalized_name = str(model_name).strip()
        normalized_version = str(version).strip()
        if not normalized_name:
            raise ValueError('model_name must be non-empty')
        if not normalized_version:
            raise ValueError('version must be non-empty')
        current = self.versions.get(normalized_name)
        if current is not None and current != normalized_version:
            raise ValueError('model version already set; use replace() for explicit migration')
        self.versions[normalized_name] = normalized_version

    def replace(self, model_name: str, version: str) -> None:
        normalized_name = str(model_name).strip()
        normalized_version = str(version).strip()
        if not normalized_name:
            raise ValueError('model_name must be non-empty')
        if not normalized_version:
            raise ValueError('version must be non-empty')
        self.versions[normalized_name] = normalized_version

    def get(self, model_name: str) -> str:
        normalized_name = str(model_name).strip()
        if normalized_name not in self.versions:
            raise KeyError(normalized_name)
        return self.versions[normalized_name]
