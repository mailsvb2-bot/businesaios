from __future__ import annotations

from dataclasses import dataclass


@dataclass
class EconomicsMetadataBuilder:
    module_name: str = "core.economics"
    schema_version: str = "v1"
    advisory_only: bool = True

    def build(self) -> dict:
        return {
            "module": self.module_name,
            "schema_version": self.schema_version,
            "advisory_only": self.advisory_only,
            "decision_boundary": "economics_enriches_and_constrains_but_never_issues_actions",
        }
