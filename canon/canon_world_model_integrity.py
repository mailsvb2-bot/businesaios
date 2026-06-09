from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

WORLD_MODEL_CANON_VERSION = "WM-CONTRACT-V1"

REQUIRED_WORLD_MODEL_CANON_FILES = (
    'docs/SYSTEM_TZ_CANONICAL.md',
    'docs/ARCHITECTURE_CANON_V20.md',
    'CONTRIBUTING.md',
    'README.md',
    'core/ai/decision_core.py',
    'runtime/executor.py',
    'runtime/boot/boot_core_assembly.py',
    'bootstrap/world_model_contract.py',
    'scripts/check_world_model_integrity.py',
    'scripts/migrate_world_model_to_canonical.py',
)

REQUIRED_WORLD_MODEL_CANON_STRINGS = {
    'docs/SYSTEM_TZ_CANONICAL.md': ('World Model Integrity', 'canonical path'),
    'docs/ARCHITECTURE_CANON_V20.md': ('World Model Integrity', 'strict pinning is enabled'),
    'CONTRIBUTING.md': ('World-model integrity is mandatory',),
    'README.md': ('CanonicalDecisionWorldModel',),
}

FORBIDDEN_WORLD_MODEL_PATTERNS = ('WorldModel(LTVModel())', 'world_model=WorldModel(')
REQUIRED_DECISIONCORE_STRINGS = ('DecisionWorldModelPort', 'world_model')
REQUIRED_EXECUTOR_STRINGS = ('extract_pinned_world_model_meta_from_payload', 'enforce_world_model_pin_or_raise')
REQUIRED_BOOT_STRINGS = ('build_and_verify_default_world_model', 'verify_boot_world_model_integrity')


@dataclass(frozen=True)
class CanonFinding:
    path: str
    kind: str
    message: str


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return ''


def scan_world_model_canon_contract(repo_root: str | Path) -> list[CanonFinding]:
    root = Path(repo_root)
    findings: list[CanonFinding] = []
    for rel in REQUIRED_WORLD_MODEL_CANON_FILES:
        if not (root / rel).exists():
            findings.append(CanonFinding(rel, 'missing-world-model-canon-file', 'Required world-model canon file is missing.'))
    for rel, tokens in REQUIRED_WORLD_MODEL_CANON_STRINGS.items():
        path = root / rel
        if not path.exists():
            findings.append(CanonFinding(rel, 'missing-world-model-canon-doc', 'Required canon document is missing.'))
            continue
        text = _read_text(path)
        for token in tokens:
            if token not in text:
                findings.append(CanonFinding(rel, 'world-model-canon-doc-drift', f'Required canon text is missing: {token}'))
    _check_decision_core(root, findings)
    _check_executor(root, findings)
    _check_boot(root, findings)
    _check_forbidden_patterns(root, findings)
    return findings


def _check_decision_core(root: Path, findings: list[CanonFinding]) -> None:
    text = _read_text(root / 'core/ai/decision_core.py')
    if not text:
        findings.append(CanonFinding('core/ai/decision_core.py', 'missing-decision-core', 'DecisionCore file missing or unreadable.'))
        return
    for token in REQUIRED_DECISIONCORE_STRINGS:
        if token not in text:
            findings.append(CanonFinding('core/ai/decision_core.py', 'decision-core-world-model-contract-drift', f'Missing required contract token: {token}'))


def _check_executor(root: Path, findings: list[CanonFinding]) -> None:
    text = _read_text(root / 'runtime/executor.py')
    if not text:
        findings.append(CanonFinding('runtime/executor.py', 'missing-runtime-executor', 'RuntimeExecutor file missing or unreadable.'))
        return
    for token in REQUIRED_EXECUTOR_STRINGS:
        if token not in text:
            findings.append(CanonFinding('runtime/executor.py', 'executor-world-model-pinning-drift', f'Missing required world-model enforcement token: {token}'))


def _check_boot(root: Path, findings: list[CanonFinding]) -> None:
    text = _read_text(root / 'runtime/boot/boot_core_assembly.py')
    if not text:
        findings.append(CanonFinding('runtime/boot/boot_core_assembly.py', 'missing-boot-core-assembly', 'boot_core_assembly.py missing or unreadable.'))
        return
    for token in REQUIRED_BOOT_STRINGS:
        if token not in text:
            findings.append(CanonFinding('runtime/boot/boot_core_assembly.py', 'boot-world-model-integrity-drift', f'Missing required world-model token: {token}'))


def _check_forbidden_patterns(root: Path, findings: list[CanonFinding]) -> None:
    targets = (root / 'core', root / 'runtime', root / 'interfaces', root / 'runtime' / 'platform', root / 'governance')
    excluded = {'world_model_forbidden_paths.py', 'migrate_world_model_to_canonical.py'}
    for base in targets:
        if not base.exists():
            continue
        for path in base.rglob('*.py'):
            rel = str(path.relative_to(root)).replace('\\', '/')
            if path.name in excluded:
                continue
            text = _read_text(path)
            for pattern in FORBIDDEN_WORLD_MODEL_PATTERNS:
                if pattern in text:
                    findings.append(CanonFinding(rel, 'forbidden-world-model-pattern', f'Forbidden pattern detected: {pattern}'))


def findings_as_dicts(items: Iterable[CanonFinding]) -> list[dict]:
    return [{'path': item.path, 'kind': item.kind, 'message': item.message} for item in items]
