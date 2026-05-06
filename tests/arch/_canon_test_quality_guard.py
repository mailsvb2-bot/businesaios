from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARCH_TEST_ROOT = ROOT / "tests" / "arch"

FORBIDDEN_SNIPPETS = ("assert true", "pass", "todo", "placeholder", "decorative")
QUALITY_SIGNAL_NAMES = (
    "ast", "parse_file", "python_files", "missing(", "exists(", "absolute_path(",
    "path.relative_to", "read_text(", "rglob(", "glob(", "_canon_",
)
EXEMPT_FILES = (
    "_canon_arch_audit_index.py",
    "_canon_boot_runtime_registry_guard.py",
    "_canon_domain_registry_guard.py",
    "_canon_test_quality_guard.py",
    "test_test_quality_no_placeholder_or_decorative_markers.py",
    "test_arch_audit_index_tracks_test_quality_pack.py",
)
MIN_TEXT_LENGTH = 120

AUDITED_PREFIXES = (
    "test_boot_registry_",
    "test_handler_registry_",
    "test_boot_runtime_registry_",
    "test_domain_registry_",
    "test_test_quality_",
    "test_arch_audit_index_tracks_",
    "test_round15_",
    "test_round16_",
    "test_round17_",
    "test_round18_",
    "test_no_decisioncore_import",
    "test_no_action_issuance",
)

@dataclass(frozen=True)
class ParsedArchTest:
    path: Path
    tree: ast.AST
    text: str

    @property
    def rel(self) -> str:
        return str(self.path.relative_to(ROOT))

def arch_test_files() -> list[Path]:
    if not ARCH_TEST_ROOT.exists():
        return []
    result=[]
    for path in ARCH_TEST_ROOT.glob("test_*.py"):
        if any(path.name.startswith(prefix) for prefix in AUDITED_PREFIXES):
            result.append(path)
    return sorted(result)

def parse_arch_test(path: Path) -> ParsedArchTest:
    text = path.read_text(encoding="utf-8")
    return ParsedArchTest(path=path, tree=ast.parse(text), text=text)

def lower(value: str) -> str:
    return value.strip().lower()

def test_function_names(tree: ast.AST) -> list[str]:
    return [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")]

def assertion_count(tree: ast.AST) -> int:
    return sum(1 for node in ast.walk(tree) if isinstance(node, ast.Assert))

def imported_module_count(tree: ast.AST) -> int:
    return sum(1 for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom)))

def call_names(tree: ast.AST) -> list[str]:
    result=[]
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                result.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                result.append(node.func.attr)
    return result

def has_quality_signal(parsed: ParsedArchTest) -> bool:
    text = lower(parsed.text)
    if any(signal in text for signal in QUALITY_SIGNAL_NAMES):
        return True
    names=[lower(name) for name in call_names(parsed.tree)]
    return any(name in {"parse","read_text","glob","rglob","exists","relative_to"} for name in names)

def has_forbidden_snippet(parsed: ParsedArchTest) -> bool:
    text = lower(parsed.text)
    return any(snippet in text for snippet in FORBIDDEN_SNIPPETS)

def suspiciously_short(parsed: ParsedArchTest) -> bool:
    return len(parsed.text.strip()) < MIN_TEXT_LENGTH

def has_real_test_functions(parsed: ParsedArchTest) -> bool:
    return len(test_function_names(parsed.tree)) >= 1

def is_import_only_like(parsed: ParsedArchTest) -> bool:
    if assertion_count(parsed.tree) == 0:
        return True
    if imported_module_count(parsed.tree) > 0 and not has_quality_signal(parsed):
        return True
    return False

def exempt(path: Path) -> bool:
    return path.name in EXEMPT_FILES
