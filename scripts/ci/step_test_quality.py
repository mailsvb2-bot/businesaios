from __future__ import annotations

import ast
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from collections.abc import Iterable

from scripts.ci.paths import repo_root

REPORT_DIR = "reports/test_quality"
JSON_REPORT = "reports/test_quality/test_quality.json"
MARKDOWN_REPORT = "reports/test_quality/test_quality.md"


@dataclass(frozen=True)
class TestQualityFinding:
    severity: str
    check_id: str
    path: str
    line: int
    message: str
    recommendation: str


@dataclass(frozen=True)
class TestQualityReport:
    ok: bool
    total_test_files: int
    total_test_functions: int
    findings: list[TestQualityFinding]


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _test_files(root: Path) -> list[Path]:
    tests = root / "tests"
    if not tests.exists():
        return []
    return sorted(path for path in tests.rglob("*.py") if "__pycache__" not in path.parts)


def _is_test_file(path: Path) -> bool:
    name = path.name
    return name.startswith("test_") or name.endswith("_test.py")


def _test_functions(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    funcs: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            funcs.append(node)
    return funcs


def _decorator_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _decorator_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return ""


def _has_reason_keyword(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    return any(keyword.arg == "reason" for keyword in node.keywords)


def _is_trivial_body(body: list[ast.stmt]) -> bool:
    meaningful = [
        stmt for stmt in body
        if not isinstance(stmt, (ast.Expr,)) or not isinstance(getattr(stmt, "value", None), ast.Constant) or stmt.value.value is not None
    ]
    if not meaningful:
        return True
    if len(meaningful) == 1 and isinstance(meaningful[0], ast.Pass):
        return True
    if len(meaningful) == 1 and isinstance(meaningful[0], ast.Expr):
        value = meaningful[0].value
        if isinstance(value, ast.Constant) and value.value is Ellipsis:
            return True
    return False


def _contains_assert_like(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Assert):
            return True
        if isinstance(child, ast.Call):
            name = _call_name(child.func)
            if name.startswith("pytest.") or ".assert" in name or name.startswith("assert_"):
                return True
        if isinstance(child, ast.With):
            for item in child.items:
                ctx = item.context_expr
                if isinstance(ctx, ast.Call) and _call_name(ctx.func) in {"pytest.raises", "pytest.warns"}:
                    return True
    return False


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _find_duplicate_test_names(funcs: Iterable[ast.FunctionDef | ast.AsyncFunctionDef]) -> dict[str, list[int]]:
    seen: dict[str, list[int]] = {}
    for func in funcs:
        seen.setdefault(func.name, []).append(func.lineno)
    return {name: lines for name, lines in seen.items() if len(lines) > 1}


def build_report() -> TestQualityReport:
    root = repo_root()
    files = _test_files(root)
    findings: list[TestQualityFinding] = []
    total_functions = 0

    for path in files:
        rel = _rel(root, path)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            findings.append(TestQualityFinding(
                "P0",
                "TEST_FILE_UNREADABLE",
                rel,
                1,
                f"Cannot read test file: {exc}",
                "Make the test file readable or remove it from the test tree.",
            ))
            continue

        if _is_test_file(path) and not text.strip():
            findings.append(TestQualityFinding(
                "P0",
                "TEST_FILE_EMPTY",
                rel,
                1,
                "Test file is empty.",
                "Delete the empty test file or add real executable checks.",
            ))
            continue

        try:
            tree = ast.parse(text, filename=rel)
        except SyntaxError as exc:
            findings.append(TestQualityFinding(
                "P0",
                "TEST_SYNTAX_ERROR",
                rel,
                exc.lineno or 1,
                f"Syntax error: {exc.msg}",
                "Fix syntax before running the full test suite.",
            ))
            continue

        funcs = _test_functions(tree)
        total_functions += len(funcs)

        if _is_test_file(path) and not funcs:
            findings.append(TestQualityFinding(
                "P1",
                "TEST_FILE_WITHOUT_TESTS",
                rel,
                1,
                "File name marks it as a test file, but no test_* functions were found.",
                "Add real test functions or rename this helper file so pytest intent is clear.",
            ))

        for name, lines in _find_duplicate_test_names(funcs).items():
            findings.append(TestQualityFinding(
                "P0",
                "DUPLICATE_TEST_NAME",
                rel,
                lines[1],
                f"Duplicate test function name `{name}` at lines {lines}.",
                "Rename duplicate tests; pytest will overwrite/collect ambiguously inside the module.",
            ))

        for func in funcs:
            if _is_trivial_body(func.body):
                findings.append(TestQualityFinding(
                    "P0",
                    "TRIVIAL_TEST_BODY",
                    rel,
                    func.lineno,
                    f"Test `{func.name}` has a trivial body.",
                    "Replace pass/ellipsis-only tests with real assertions.",
                ))

            for decorator in func.decorator_list:
                name = _decorator_name(decorator)
                if name in {"pytest.mark.skip", "pytest.mark.xfail"} and not _has_reason_keyword(decorator):
                    findings.append(TestQualityFinding(
                        "P1",
                        "SKIP_OR_XFAIL_WITHOUT_REASON",
                        rel,
                        func.lineno,
                        f"Test `{func.name}` uses `{name}` without an explicit reason.",
                        "Add a reason or remove the skip/xfail.",
                    ))

            if not _contains_assert_like(func):
                findings.append(TestQualityFinding(
                    "P2",
                    "TEST_WITHOUT_ASSERT_LIKE_CHECK",
                    rel,
                    func.lineno,
                    f"Test `{func.name}` has no obvious assert/pytest assertion.",
                    "Confirm this is an intentional smoke/import test, or add an explicit assertion.",
                ))

    ok = not any(f.severity == "P0" for f in findings)
    return TestQualityReport(
        ok=ok,
        total_test_files=len(files),
        total_test_functions=total_functions,
        findings=findings,
    )


def _write_reports(report: TestQualityReport) -> None:
    root = repo_root()
    report_dir = root / REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)

    (root / JSON_REPORT).write_text(
        json.dumps(asdict(report), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# BusinessAIOS Test Quality Report",
        "",
        f"ok: `{report.ok}`",
        f"total_test_files: `{report.total_test_files}`",
        f"total_test_functions: `{report.total_test_functions}`",
        "",
        "## Findings",
        "",
    ]
    if not report.findings:
        lines.append("No findings.")
    else:
        for finding in report.findings[:500]:
            lines.append(
                f"- **{finding.severity} {finding.check_id}** "
                f"`{finding.path}:{finding.line}` — {finding.message} "
                f"Recommendation: {finding.recommendation}"
            )
        if len(report.findings) > 500:
            lines.append(f"- ... truncated {len(report.findings) - 500} finding(s)")

    (root / MARKDOWN_REPORT).write_text("\n".join(lines) + "\n", encoding="utf-8")


def run() -> tuple[bool, str]:
    report = build_report()
    _write_reports(report)
    if report.ok:
        return True, (
            f"test quality passed; files={report.total_test_files} "
            f"tests={report.total_test_functions} findings={len(report.findings)}"
        )
    return False, (
        f"test quality failed; files={report.total_test_files} "
        f"tests={report.total_test_functions} findings={len(report.findings)}; "
        f"see {JSON_REPORT}"
    )


__all__ = ["run", "build_report"]
