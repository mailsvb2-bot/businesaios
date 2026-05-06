"""Helpers for repo certification: IO, AST analysis, report."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

from scripts.certify_ast import (
    function_cyclomatic_complexity,
    is_public_name,
    parse_import_bases as parse_import_bases_from_text,
)
from scripts.certify_io import count_lines, iter_py_files, read_text
from scripts.certify_report import CertificationReport, TRUTHY

def parse_import_bases(py: Path) -> Set[str]:
    """Return top-level imported base module names for a python file."""
    return parse_import_bases_from_text(read_text(py))


def find_network_imports_outside_sealed(root: Path) -> List[Tuple[str, str]]:
    """Forbidden network libs outside runtime/_internal."""
    forbidden = {"httpx", "requests", "aiohttp", "urllib3", "openai", "telegram", "telebot"}
    allowed_dir = (root / "runtime" / "_internal").resolve()

    findings: List[Tuple[str, str]] = []
    for p in iter_py_files(root):
        rp = p.resolve()
        if allowed_dir in rp.parents or rp == allowed_dir:
            continue

        for base in parse_import_bases(p):
            if base in forbidden:
                findings.append((str(p.relative_to(root)), base))

    return findings



def check_god_modules(root: Path) -> List[str]:
    """Warn on unusually large modules."""
    allow = {
        "runtime/_internal/_effects_impl.py",
        "runtime/boot/system_builder.py",
        "interfaces/telegram/outbound/outbound_queue.py",
    }

    warnings: List[str] = []
    for p in iter_py_files(root):
        rel = str(p.relative_to(root).as_posix())
        if rel in allow:
            continue
        n = count_lines(p)
        if n >= 2500:
            warnings.append(f"god-module risk: {rel} has {n} LOC")
    return warnings


def analyze_god_objects_and_complexity(root: Path) -> Tuple[List[str], List[str]]:
    """Return (warnings, signals) for god-objects / complexity."""
    targets = {"core", "runtime", "interfaces", "runtime.platform"}
    warnings: List[str] = []
    signals: List[str] = []

    for p in iter_py_files(root):
        rel = p.relative_to(root).as_posix()
        top = rel.split("/", 1)[0]
        if top not in targets:
            continue
        if rel.startswith("tests/") or rel.startswith("docs/"):
            continue
        if rel.endswith("/__init__.py") or rel.endswith("__init__.py"):
            continue

        src = read_text(p)
        if not src.strip():
            continue
        try:
            tree = ast.parse(src)
        except Exception:
            continue

        loc = count_lines(p)
        if loc >= 3500:
            (warnings if loc >= 8000 else signals).append(
                f"very large module: {rel} has {loc} LOC"
            )

        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue

            pub_methods = 0
            max_fn_complexity = 0
            pub_attrs = 0

            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if is_public_name(item.name):
                        pub_methods += 1
                    max_fn_complexity = max(
                        max_fn_complexity, function_cyclomatic_complexity(item)
                    )
                elif isinstance(item, ast.Assign):
                    for t in item.targets:
                        if isinstance(t, ast.Name) and is_public_name(t.id):
                            pub_attrs += 1

            if pub_methods >= 120:
                warnings.append(
                    f"god-object: {rel}::{node.name} has {pub_methods} public methods"
                )
            elif pub_methods >= 25:
                signals.append(
                    f"god-object signal: {rel}::{node.name} has {pub_methods} public methods"
                )

            if pub_attrs >= 200:
                warnings.append(
                    f"god-object: {rel}::{node.name} exposes {pub_attrs} public attrs"
                )
            elif pub_attrs >= 35:
                signals.append(
                    f"large surface signal: {rel}::{node.name} exposes {pub_attrs} public attrs"
                )

            if max_fn_complexity >= 200:
                warnings.append(
                    f"high complexity: {rel}::{node.name} has method complexity up to {max_fn_complexity}"
                )
            elif max_fn_complexity >= 25:
                signals.append(
                    f"complexity signal: {rel}::{node.name} has method complexity up to {max_fn_complexity}"
                )

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not is_public_name(node.name):
                    continue
                c = function_cyclomatic_complexity(node)
                if c >= 200:
                    warnings.append(
                        f"high complexity: {rel}::{node.name} has complexity {c}"
                    )
                elif c >= 25:
                    signals.append(
                        f"complexity signal: {rel}::{node.name} has complexity {c}"
                    )

    return warnings, signals


def detect_policy_divergence_signals(root: Path) -> List[str]:
    """Heuristics to flag potential double policy or duplicated routing."""
    signals: List[str] = []
    policy_classes_by_dir: Dict[str, List[str]] = {}

    for p in iter_py_files(root):
        rel = p.relative_to(root).as_posix()
        if rel.startswith("tests/") or rel.startswith("docs/"):
            continue

        src = read_text(p)
        if not src.strip():
            continue
        try:
            tree = ast.parse(src)
        except Exception:
            continue

        policies: List[str] = []
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name.lower().endswith("policy"):
                policies.append(node.name)

        if policies:
            d = str(p.parent.relative_to(root).as_posix())
            policy_classes_by_dir.setdefault(d, []).extend(
                [f"{p.name}:{n}" for n in policies]
            )

        route_like = 0
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        nm = t.id.upper()
                        if nm in {
                            "ROUTES",
                            "HANDLERS",
                            "CALLBACKS",
                            "CALLBACK_ROUTES",
                            "ROUTER",
                        }:
                            route_like += 1
        if route_like >= 2:
            signals.append(
                f"possible double routing maps: {rel} defines {route_like} route-like globals"
            )

    for d, items in sorted(policy_classes_by_dir.items()):
        if len(items) >= 3:
            signals.append(
                f"policy density signal: {d} contains {len(items)} Policy classes ({', '.join(items[:6])}...)"
            )

    return signals
