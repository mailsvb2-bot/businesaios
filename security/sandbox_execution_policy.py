from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


CANON_SANDBOX_EXECUTION_POLICY = True


@dataclass(frozen=True)
class SandboxExecutionVerdict:
    allowed: bool
    reason: str
    max_cpu_seconds: int
    max_memory_mb: int
    network_allowed: bool
    filesystem_write_allowed: bool
    labels: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SandboxExecutionPolicy:
    max_cpu_seconds: int = 5
    max_memory_mb: int = 256
    allow_network: bool = False
    allow_filesystem_write: bool = False
    allowed_modules_prefixes: tuple[str, ...] = ('math', 'json', 'datetime', 'collections')
    blocked_modules_prefixes: tuple[str, ...] = (
        'socket', 'subprocess', 'requests', 'httpx', 'aiohttp', 'urllib', 'os', 'shutil', 'pathlib', 'ctypes'
    )

    def validate(self) -> None:
        if int(self.max_cpu_seconds) <= 0:
            raise ValueError('max_cpu_seconds must be > 0')
        if int(self.max_memory_mb) <= 0:
            raise ValueError('max_memory_mb must be > 0')

    def evaluate(self, *, requested_modules: tuple[str, ...], requests_network: bool, requests_filesystem_write: bool) -> SandboxExecutionVerdict:
        self.validate()
        blocked = [module for module in requested_modules if self._is_blocked(module)]
        if blocked:
            return SandboxExecutionVerdict(
                allowed=False,
                reason='blocked_module',
                max_cpu_seconds=int(self.max_cpu_seconds),
                max_memory_mb=int(self.max_memory_mb),
                network_allowed=False,
                filesystem_write_allowed=False,
                labels={'modules': ','.join(sorted(blocked))},
            )
        if requests_network and not self.allow_network:
            return SandboxExecutionVerdict(
                allowed=False,
                reason='network_not_allowed',
                max_cpu_seconds=int(self.max_cpu_seconds),
                max_memory_mb=int(self.max_memory_mb),
                network_allowed=False,
                filesystem_write_allowed=bool(self.allow_filesystem_write),
            )
        if requests_filesystem_write and not self.allow_filesystem_write:
            return SandboxExecutionVerdict(
                allowed=False,
                reason='filesystem_write_not_allowed',
                max_cpu_seconds=int(self.max_cpu_seconds),
                max_memory_mb=int(self.max_memory_mb),
                network_allowed=bool(self.allow_network),
                filesystem_write_allowed=False,
            )
        disallowed_by_default = [module for module in requested_modules if not self._is_allowed(module)]
        if disallowed_by_default:
            return SandboxExecutionVerdict(
                allowed=False,
                reason='module_not_allowlisted',
                max_cpu_seconds=int(self.max_cpu_seconds),
                max_memory_mb=int(self.max_memory_mb),
                network_allowed=bool(self.allow_network),
                filesystem_write_allowed=bool(self.allow_filesystem_write),
                labels={'modules': ','.join(sorted(disallowed_by_default))},
            )
        return SandboxExecutionVerdict(
            allowed=True,
            reason='ok',
            max_cpu_seconds=int(self.max_cpu_seconds),
            max_memory_mb=int(self.max_memory_mb),
            network_allowed=bool(self.allow_network),
            filesystem_write_allowed=bool(self.allow_filesystem_write),
        )

    def _is_allowed(self, module: str) -> bool:
        return any(str(module).startswith(prefix) for prefix in self.allowed_modules_prefixes)

    def _is_blocked(self, module: str) -> bool:
        return any(str(module).startswith(prefix) for prefix in self.blocked_modules_prefixes)


__all__ = [
    'CANON_SANDBOX_EXECUTION_POLICY',
    'SandboxExecutionPolicy',
    'SandboxExecutionVerdict',
]
