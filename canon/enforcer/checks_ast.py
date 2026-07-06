from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Any

from canon.enforcer.ast_semantics import full_attr_name, looks_like_integration_stub
from canon.enforcer.rules import (
    BUSINESS_HINT_RE,
    CRITICAL_SILENT_FAIL_PATTERNS,
    FORBIDDEN_DECISION_FUNCTION_NAMES_OUTSIDE_CORE,
    FORBIDDEN_EFFECT_CALL_TAILS_IN_CORE,
    FORBIDDEN_IMPORT_PREFIXES_IN_CORE,
    GOD_MODULE_FUNC_THRESHOLD,
    GOD_MODULE_IMPORT_THRESHOLD,
    GOD_MODULE_LINE_THRESHOLD,
    MAGIC_NUMBER_RE,
    REPO_ROOT,
    is_critical_path,
    iter_py_files,
    path_str,
    safe_read_text,
)
from canon.enforcer.rules import (
    iter_todo_lines as _iter_todo_lines,
)


def check_ast_semantics(report: Any, root: Path = REPO_ROOT) -> None:
    for path in iter_py_files(root):
        rel = path_str(path)
        text = safe_read_text(path)

        try:
            tree = ast.parse(text, filename=rel)
        except SyntaxError as e:
            report.add(
                severity="critical",
                kind="syntax-error",
                path=rel,
                line=e.lineno,
                message=str(e),
                hint="Fix syntax before any architectural work continues.",
            )
            continue

        lines = text.count("\n") + 1
        funcs = sum(isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) for n in ast.walk(tree))
        imports = sum(isinstance(n, ast.Import | ast.ImportFrom) for n in ast.walk(tree))
        if (
            lines > GOD_MODULE_LINE_THRESHOLD
            or funcs > GOD_MODULE_FUNC_THRESHOLD
            or imports > GOD_MODULE_IMPORT_THRESHOLD
        ):
            report.add(
                severity="medium",
                kind="god-module-risk",
                path=rel,
                line=None,
                message=(
                    f"Large module detected (lines={lines}, funcs={funcs}, imports={imports})."
                ),
                hint="Split by role into small explicit modules.",
            )

        if is_critical_path(rel):
            for snippet in CRITICAL_SILENT_FAIL_PATTERNS:
                if snippet in text:
                    report.add(
                        severity="high",
                        kind="silent-failure",
                        path=rel,
                        line=None,
                        message="Silent exception swallowing in critical path.",
                        hint="Replace with structured log + audit/proof event + explicit failure outcome.",
                    )
                    break
        # Fake-ready integrations: AST-driven to avoid false positives from prose/comments.
        if rel.startswith("interfaces/"):
            for node in ast.walk(tree):
                if looks_like_integration_stub(node):
                    report.add(
                        severity="high",
                        kind="fake-ready-integration",
                        path=rel,
                        line=getattr(node, "lineno", None),
                        message=f"Suspicious integration stub detected in function: {getattr(node, 'name', '<unknown>')}",
                        hint="Fail honestly with Unsupported*/NotWired* or implement the real contract.",
                    )
                    break
            else:
                for line_no in _iter_todo_lines(text):
                    report.add(
                        severity="medium",
                        kind="fake-ready-integration",
                        path=rel,
                        line=line_no,
                        message="TODO marker found in integration path.",
                        hint="Replace TODO with explicit Unsupported*/NotWired* or implement the real contract.",
                    )
                    break

        if rel.startswith("core/") and BUSINESS_HINT_RE.search(text) and MAGIC_NUMBER_RE.search(text):
            report.add(
                severity="medium",
                kind="hidden-business-logic",
                path=rel,
                line=None,
                message="Business-looking terms mixed with hardcoded numeric literals.",
                hint="Move thresholds and strategy knobs into typed config/policy objects.",
            )

        for node in ast.walk(tree):
            if rel.startswith("core/"):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith(FORBIDDEN_IMPORT_PREFIXES_IN_CORE):
                            report.add(
                                severity="critical",
                                kind="core-side-effect-import",
                                path=rel,
                                line=node.lineno,
                                message=f"Forbidden import in core: {alias.name}",
                                hint="Network/process side effects must not live in core.",
                            )

                if isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if module.startswith(FORBIDDEN_IMPORT_PREFIXES_IN_CORE):
                        report.add(
                            severity="critical",
                            kind="core-side-effect-import",
                            path=rel,
                            line=node.lineno,
                            message=f"Forbidden from-import in core: {module}",
                            hint="Network/process side effects must not live in core.",
                        )

                if isinstance(node, ast.Call):
                    fn = full_attr_name(node.func)
                    tail = fn.split(".")[-1].lower() if fn else ""
                    lowered = fn.lower()
                    if tail in FORBIDDEN_EFFECT_CALL_TAILS_IN_CORE and any(token in lowered for token in ("provider", "connector", "client", "http", "requests", "api")):
                        report.add(
                            severity="critical",
                            kind="core-side-effect-call",
                            path=rel,
                            line=getattr(node, "lineno", None),
                            message=f"Forbidden effect-like call in core: {fn}",
                            hint="Core must produce proposals, not execute effects.",
                        )

                    infra_name_re = re.compile(r"(?:^|[._])(connector|client|provider)(?:$|[._])")
                    if infra_name_re.search(lowered):
                        report.add(
                            severity="high",
                            kind="core-infra-call",
                            path=rel,
                            line=getattr(node, "lineno", None),
                            message=f"Suspicious direct infra call from core: {fn}",
                            hint="Call infra only through runtime handler/effect ports.",
                        )

            if rel.startswith("runtime/"):
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name in FORBIDDEN_DECISION_FUNCTION_NAMES_OUTSIDE_CORE:
                    report.add(
                        severity="critical",
                        kind="runtime-decision-logic",
                        path=rel,
                        line=node.lineno,
                        message=f"Runtime defines forbidden decision-like function: {node.name}",
                        hint="Move decision logic into core/ai/decision_core.py.",
                    )

                if isinstance(node, ast.Call):
                    fn = full_attr_name(node.func)
                    tail = fn.split(".")[-1] if fn else ""
                    if tail in FORBIDDEN_DECISION_FUNCTION_NAMES_OUTSIDE_CORE:
                        report.add(
                            severity="critical",
                            kind="runtime-decision-call",
                            path=rel,
                            line=getattr(node, "lineno", None),
                            message=f"Runtime calls decision-like function: {fn}",
                            hint="Runtime must execute typed actions, not decide them.",
                        )
