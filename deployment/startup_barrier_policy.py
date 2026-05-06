from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping
import os


CANON_DEPLOYMENT_STARTUP_BARRIER_POLICY = True

_ALLOWED_APP_ENVS = frozenset({"dev", "test", "stage", "staging", "prod", "production"})


@dataclass(frozen=True)
class StartupBarrierViolation:
    code: str
    message: str
    details: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.code or "").strip():
            raise ValueError("startup barrier violation code is required")
        if not str(self.message or "").strip():
            raise ValueError("startup barrier violation message is required")


@dataclass(frozen=True)
class StartupBarrierReport:
    violations: tuple[StartupBarrierViolation, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not self.violations

    def summaries(self) -> tuple[str, ...]:
        return tuple(item.message for item in self.violations)


@dataclass(frozen=True)
class StartupBarrierPolicy:
    required_env: tuple[str, ...] = field(default_factory=tuple)
    forbidden_env: tuple[str, ...] = field(default_factory=tuple)
    required_paths: tuple[str, ...] = field(default_factory=tuple)
    required_directories: tuple[str, ...] = field(default_factory=lambda: ("boot", "runtime", "config"))
    required_files: tuple[str, ...] = field(default_factory=lambda: ("VERSION", "RELEASE_TAG"))
    allow_prod_without_release_tag: bool = False
    require_release_manifest_in_prod: bool = True
    repo_root: str | Path = "."

    def __post_init__(self) -> None:
        for field_name in ("required_env", "forbidden_env", "required_paths", "required_directories", "required_files"):
            values = tuple(str(item) for item in getattr(self, field_name))
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must be unique")

    def _normalize_env(self, environ: Mapping[str, str] | None = None) -> dict[str, str]:
        return dict(os.environ if environ is None else environ)

    def _resolve(self, raw_path: str) -> Path:
        path = Path(raw_path)
        base = Path(self.repo_root).resolve()
        resolved = path if path.is_absolute() else (base / path)
        resolved = resolved.resolve()
        try:
            resolved.relative_to(base)
        except ValueError as exc:
            raise ValueError(f"startup barrier path escapes repo_root: {raw_path}") from exc
        return resolved

    def validate_environment(self, environ: Mapping[str, str] | None = None) -> StartupBarrierReport:
        env = self._normalize_env(environ)
        violations: list[StartupBarrierViolation] = []
        for key in self.required_env:
            if not str(env.get(key, "")).strip():
                violations.append(
                    StartupBarrierViolation(
                        code="missing_env",
                        message=f"required env missing: {key}",
                        details={"env": key},
                    )
                )
        for key in self.forbidden_env:
            value = str(env.get(key, "")).strip()
            if value:
                violations.append(
                    StartupBarrierViolation(
                        code="forbidden_env",
                        message=f"forbidden env present: {key}",
                        details={"env": key, "value": value},
                    )
                )
        raw_app_env = str(env.get("APP_ENV", env.get("ENV", "dev"))).strip().lower()
        if raw_app_env and raw_app_env not in _ALLOWED_APP_ENVS:
            violations.append(
                StartupBarrierViolation(
                    code="invalid_app_env",
                    message=f"APP_ENV has unsupported value: {raw_app_env}",
                    details={"value": raw_app_env, "allowed": tuple(sorted(_ALLOWED_APP_ENVS))},
                )
            )
        normalized_app_env = "prod" if raw_app_env == "production" else raw_app_env
        if normalized_app_env == "prod":
            if not self.allow_prod_without_release_tag and not str(env.get("RELEASE_TAG", "")).strip():
                violations.append(
                    StartupBarrierViolation(
                        code="release_tag_required",
                        message="RELEASE_TAG is required in prod",
                        details={"env": "RELEASE_TAG"},
                    )
                )
            if str(env.get("DEBUG", "")).strip().lower() in {"1", "true", "yes", "on"}:
                violations.append(
                    StartupBarrierViolation(
                        code="debug_forbidden_in_prod",
                        message="DEBUG must not be enabled in prod",
                        details={"env": "DEBUG", "value": env.get("DEBUG")},
                    )
                )
            if self.require_release_manifest_in_prod and not self._resolve("release/manifest.json").exists():
                violations.append(
                    StartupBarrierViolation(
                        code="release_manifest_missing",
                        message="release/manifest.json is required in prod",
                        details={"path": str(self._resolve('release/manifest.json'))},
                    )
                )
        for raw_path in self.required_paths:
            path = self._resolve(raw_path)
            if not path.exists():
                violations.append(
                    StartupBarrierViolation(
                        code="missing_path",
                        message=f"required path missing: {raw_path}",
                        details={"path": str(path)},
                    )
                )
        for raw_path in self.required_directories:
            path = self._resolve(raw_path)
            if not path.exists():
                violations.append(
                    StartupBarrierViolation(
                        code="missing_directory",
                        message=f"required directory missing: {raw_path}",
                        details={"path": str(path)},
                    )
                )
            elif not path.is_dir():
                violations.append(
                    StartupBarrierViolation(
                        code="directory_expected",
                        message=f"required directory is not a directory: {raw_path}",
                        details={"path": str(path)},
                    )
                )
        for raw_path in self.required_files:
            path = self._resolve(raw_path)
            if not path.exists():
                violations.append(
                    StartupBarrierViolation(
                        code="missing_file",
                        message=f"required file missing: {raw_path}",
                        details={"path": str(path)},
                    )
                )
            elif not path.is_file():
                violations.append(
                    StartupBarrierViolation(
                        code="file_expected",
                        message=f"required file is not a file: {raw_path}",
                        details={"path": str(path)},
                    )
                )
        return StartupBarrierReport(violations=tuple(violations))

    def assert_environment(self, environ: Mapping[str, str] | None = None) -> None:
        report = self.validate_environment(environ=environ)
        if report.violations:
            raise RuntimeError("startup barrier policy failed: " + "; ".join(report.summaries()))


__all__ = [
    "CANON_DEPLOYMENT_STARTUP_BARRIER_POLICY",
    "StartupBarrierPolicy",
    "StartupBarrierReport",
    "StartupBarrierViolation",
]
