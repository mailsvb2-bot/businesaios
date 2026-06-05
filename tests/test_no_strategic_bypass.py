from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

# ============================================================
# CONFIG
# ============================================================

# Canonical strategic engine file (single source of truth)
CANON_ENGINE_REL = Path("core/strategic_horizon/engine.py")

# Names that must exist ONLY in the canonical engine module
SINGLETON_SYMBOLS = {
    "StrategicHorizonEngine",
    "StrategicMode",
    "LearningRegime",
    "SystemState",
    "StrategicVector",
}

# Enum members that must not be re-declared elsewhere as strategic regime enums
CANON_MODE_MEMBERS = {"DEFENSE", "STABILIZE", "OPTIMIZE", "EXPAND", "RESEARCH"}

# Common folders to ignore
IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    ".tox",
    ".eggs",
    "site-packages",
    "node_modules",
}

# Files where duplication is allowed (tests may import symbols, but must not redefine them)
ALLOW_REDEFS_IN = {
    CANON_ENGINE_REL,
}

# Optional: allow these files to contain string literals like "stabilize"/"defense" (docs, configs)
ALLOW_MODE_LITERALS_IN_DIRS = {
    Path("docs"),
    Path("core/finance/strategic/scenarios"),
}

MODE_STRING_LITERALS = {"stabilize", "optimize", "expand", "research", "defense"}


# ============================================================
# HELPERS
# ============================================================

def _repo_root() -> Path:
    # tests/ is expected at <repo_root>/tests/
    return Path(__file__).resolve().parents[1]


def _iter_py_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*.py"):
        # ignore hidden/known dirs
        if any(part in IGNORE_DIRS for part in p.parts):
            continue
        yield p


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


@dataclass(frozen=True)
class FileFindings:
    rel: Path
    defined_singletons: frozenset[str]
    suspicious_regime_enum: bool
    has_mode_literals: bool


def _is_enum_class(node: ast.ClassDef) -> bool:
    # Enum can appear as `Enum` or `enum.Enum` or `str, Enum`
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id == "Enum":
            return True
        if isinstance(base, ast.Attribute) and base.attr == "Enum":
            return True
    return False


def _enum_members(node: ast.ClassDef) -> set[str]:
    members: set[str] = set()
    for stmt in node.body:
        # members are typically Assign targets
        if isinstance(stmt, ast.Assign):
            for t in stmt.targets:
                if isinstance(t, ast.Name):
                    members.add(t.id)
        elif isinstance(stmt, ast.AnnAssign):
            if isinstance(stmt.target, ast.Name):
                members.add(stmt.target.id)
    return members


def _collect_findings(root: Path, file_path: Path) -> FileFindings:
    rel = file_path.relative_to(root)
    src = _read_text(file_path)

    try:
        tree = ast.parse(src, filename=str(rel))
    except SyntaxError:
        # If repo contains invalid syntax, that's a separate failure;
        # treat as no findings here and let other tests catch syntax errors.
        return FileFindings(rel=rel, defined_singletons=frozenset(), suspicious_regime_enum=False, has_mode_literals=False)

    defined: set[str] = set()
    suspicious_regime_enum = False

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            defined.add(node.name)

            if _is_enum_class(node):
                members = _enum_members(node)
                # If it looks like our StrategicMode enum re-declared somewhere else -> bypass
                if CANON_MODE_MEMBERS.issubset(members) or (len(CANON_MODE_MEMBERS.intersection(members)) >= 4):
                    suspicious_regime_enum = True

        elif isinstance(node, ast.FunctionDef):
            defined.add(node.name)

        elif isinstance(node, ast.AsyncFunctionDef):
            defined.add(node.name)

    # Mode literals check (soft bypass signal). We inspect real string constants
    # instead of raw source substrings to avoid false positives like Path.expanduser
    # or method names such as optimize().
    mode_values: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            mode_values.add(node.value.casefold())
    has_mode_literals = any(lit in mode_values for lit in MODE_STRING_LITERALS)

    return FileFindings(
        rel=rel,
        defined_singletons=frozenset(defined.intersection(SINGLETON_SYMBOLS)),
        suspicious_regime_enum=suspicious_regime_enum,
        has_mode_literals=has_mode_literals,
    )


def _is_allowed_mode_literals(rel: Path) -> bool:
    # Allow docs/ or other explicitly allowed dirs
    for d in ALLOW_MODE_LITERALS_IN_DIRS:
        try:
            rel.relative_to(d)
            return True
        except ValueError:
            pass
    return False


# ============================================================
# TESTS
# ============================================================

def test_strategic_engine_is_single_source_of_truth_file_exists():
    root = _repo_root()
    engine = root / CANON_ENGINE_REL
    assert engine.exists(), f"Canonical engine file not found: {CANON_ENGINE_REL}"


def test_no_redefinition_of_strategic_singletons_outside_engine():
    """
    Hard rule:
    StrategicHorizonEngine / StrategicMode / LearningRegime / SystemState / StrategicVector
    must be defined ONLY in core/strategic_horizon/engine.py
    """
    root = _repo_root()
    offenders: list[tuple[Path, set[str]]] = []

    for p in _iter_py_files(root):
        rel = p.relative_to(root)

        findings = _collect_findings(root, p)
        if not findings.defined_singletons:
            continue

        if rel in ALLOW_REDEFS_IN:
            continue

        offenders.append((rel, set(findings.defined_singletons)))

    assert not offenders, (
        "Strategic singleton symbols must not be re-defined outside the canonical engine.\n"
        + "\n".join([f"- {rel}: {sorted(names)}" for rel, names in offenders])
    )


def test_no_regime_enum_duplication_outside_engine():
    """
    Hard rule:
    No other Enum in the repo should replicate the strategic regime members set,
    otherwise it's a Strategic Bypass (alternate strategy center).
    """
    root = _repo_root()
    offenders: list[Path] = []

    for p in _iter_py_files(root):
        rel = p.relative_to(root)
        if rel in ALLOW_REDEFS_IN:
            continue

        findings = _collect_findings(root, p)
        if findings.suspicious_regime_enum:
            offenders.append(rel)

    assert not offenders, (
        "Suspicious StrategicMode-like Enum re-declared outside canonical engine (Strategic Bypass).\n"
        + "\n".join([f"- {rel}" for rel in offenders])
    )


def test_no_mode_string_literals_outside_allowed_locations():
    """
    Soft-but-useful guard:
    If someone starts sprinkling raw literals 'stabilize/defense/...'
    across business code, that's usually bypass drift.

    This test flags such literals outside engine.py and allowed docs/config directories.
    """
    root = _repo_root()
    offenders: list[Path] = []

    for p in _iter_py_files(root):
        rel = p.relative_to(root)

        if rel == CANON_ENGINE_REL:
            continue
        if _is_allowed_mode_literals(rel):
            continue

        findings = _collect_findings(root, p)
        if findings.has_mode_literals:
            # allow tests to mention literals if they import/validate (optional):
            if rel.parts and rel.parts[0] == "tests":
                continue
            offenders.append(rel)

    assert not offenders, (
        "Raw strategic mode literals found outside canonical engine (possible bypass drift).\n"
        "If you really need them (rare), move them into engine constants or add an explicit allowlist.\n"
        + "\n".join([f"- {rel}" for rel in offenders])
    )
