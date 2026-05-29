from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass, field
from typing import Mapping

CANON_ENVIRONMENT_MATRIX = True

_ENVIRONMENT_ALIASES = {
    "development": "dev",
    "local": "dev",
    "staging": "stage",
    "preprod": "stage",
    "production": "prod",
}


def normalize_environment_name(value: str) -> str:
    raw = str(value or "").strip().lower()
    return _ENVIRONMENT_ALIASES.get(raw, raw)


@dataclass(frozen=True)
class EnvironmentMatrixRow:
    environment: str
    deployment_tier: str
    strict_secrets: bool = True
    allow_demo_effects: bool = False
    require_signed_requests: bool = True
    require_human_approval_for_prod_mutations: bool = True
    default_feature_flags: Mapping[str, bool] = field(default_factory=dict)
    labels: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if not normalize_environment_name(self.environment):
            raise ValueError("environment is required")
        if not str(self.deployment_tier or "").strip():
            raise ValueError("deployment_tier is required")
        for key in self.default_feature_flags.keys():
            if not str(key or "").strip():
                raise ValueError("default feature flag keys must be non-empty")

    @property
    def normalized_environment(self) -> str:
        return normalize_environment_name(self.environment)


@dataclass(frozen=True)
class EnvironmentMatrix:
    rows: tuple[EnvironmentMatrixRow, ...] = field(default_factory=tuple)

    def validate(self) -> None:
        seen: set[str] = set()
        for row in self.rows:
            row.validate()
            key = row.normalized_environment
            if key in seen:
                raise ValueError(f"duplicate environment row: {row.environment}")
            seen.add(key)

    def get(self, environment: str) -> EnvironmentMatrixRow | None:
        lookup = normalize_environment_name(environment)
        for row in self.rows:
            if row.normalized_environment == lookup:
                return row
        return None

    def require(self, environment: str) -> EnvironmentMatrixRow:
        row = self.get(environment)
        if row is None:
            raise KeyError(f"unknown environment: {environment}")
        return row

    @classmethod
    def default(cls) -> EnvironmentMatrix:
        matrix = cls(
            rows=(
                EnvironmentMatrixRow(
                    environment="dev",
                    deployment_tier="local",
                    strict_secrets=False,
                    allow_demo_effects=True,
                    require_signed_requests=False,
                    require_human_approval_for_prod_mutations=False,
                    default_feature_flags={"debug_routes": True, "unsafe_demo_effects": True},
                    labels={"risk": "low", "change_gate": "open"},
                ),
                EnvironmentMatrixRow(
                    environment="stage",
                    deployment_tier="preprod",
                    strict_secrets=True,
                    allow_demo_effects=False,
                    require_signed_requests=True,
                    require_human_approval_for_prod_mutations=True,
                    default_feature_flags={"debug_routes": False, "unsafe_demo_effects": False},
                    labels={"risk": "medium", "change_gate": "reviewed"},
                ),
                EnvironmentMatrixRow(
                    environment="prod",
                    deployment_tier="production",
                    strict_secrets=True,
                    allow_demo_effects=False,
                    require_signed_requests=True,
                    require_human_approval_for_prod_mutations=True,
                    default_feature_flags={"debug_routes": False, "unsafe_demo_effects": False},
                    labels={"risk": "high", "change_gate": "approved"},
                ),
            )
        )
        matrix.validate()
        return matrix


__all__ = [
    "CANON_ENVIRONMENT_MATRIX",
    "EnvironmentMatrix",
    "EnvironmentMatrixRow",
    "normalize_environment_name",
]
