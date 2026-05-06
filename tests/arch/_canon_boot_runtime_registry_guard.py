from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOOT_ROOT = ROOT / "runtime" / "boot"
HANDLERS_ROOT = ROOT / "runtime" / "handlers"

BOOT_MARKER = "CANON_BOOT_WIRING_ONLY"
HANDLER_MARKER = "CANON_THIN_HANDLER"

BOOT_ENTRY_PREFIXES = ("register", "wire", "bind", "assemble", "compose", "build_")
HANDLER_ENTRY_PREFIXES = ("handle",)


@dataclass(frozen=True)
class ParsedFile:
    path: Path
    tree: ast.AST

    @property
    def rel(self) -> str:
        return str(self.path.relative_to(ROOT))


def python_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.py") if path.is_file())


def parse_file(path: Path) -> ParsedFile:
    return ParsedFile(path=path, tree=ast.parse(path.read_text(encoding="utf-8")))


def function_names(tree: ast.AST) -> list[str]:
    return [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]


def assigned_constant_names(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.append(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.append(node.target.id)
    return names


def has_marker(tree: ast.AST, marker_name: str) -> bool:
    return marker_name in assigned_constant_names(tree)


def has_function_with_prefix(tree: ast.AST, prefixes: tuple[str, ...]) -> bool:
    return any(name.startswith(prefixes) for name in function_names(tree))


def audited_boot_entrypoints() -> list[Path]:
    files: list[Path] = []
    for path in python_files(BOOT_ROOT):
        rel_parts = path.relative_to(BOOT_ROOT).parts
        if path.name == "__init__.py" or any(part.startswith("_") for part in rel_parts):
            continue
        parsed = parse_file(path)
        if has_function_with_prefix(parsed.tree, BOOT_ENTRY_PREFIXES):
            files.append(path)
    return files


def audited_handler_entrypoints() -> list[Path]:
    files: list[Path] = []
    for path in python_files(HANDLERS_ROOT):
        rel_parts = path.relative_to(HANDLERS_ROOT).parts
        if path.name == "__init__.py" or any(part.startswith("_") for part in rel_parts):
            continue
        parsed = parse_file(path)
        if has_function_with_prefix(parsed.tree, HANDLER_ENTRY_PREFIXES):
            files.append(path)
    return files
