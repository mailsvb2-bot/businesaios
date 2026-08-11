from __future__ import annotations

import base64
import hashlib
import io
import json
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

from scripts.ci.paths import repo_root

BROWSER_EVIDENCE_NAME = "browser-e2e-evidence.json"
BROWSER_EVIDENCE_SCHEMA = "businessaios_browser_e2e.v2"
BROWSER_PROJECT_MATRIX = "frontend/e2e/project-matrix.json"
BROWSER_PROJECT_MATRIX_SCHEMA = "businessaios_browser_project_matrix.v2"
_HTML_REPORT_MARKER = '<template id="playwrightReportBase64">data:application/zip;base64,'


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _integer(value: object) -> int:
    if type(value) is int:
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return -1


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _matrix_snapshot() -> tuple[list[dict[str, str]], tuple[tuple[str, str], ...], str] | None:
    try:
        raw = (repo_root() / BROWSER_PROJECT_MATRIX).read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    projects = payload.get("projects") if isinstance(payload, dict) else None
    scenarios = payload.get("scenarios") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict) or payload.get("schema") != BROWSER_PROJECT_MATRIX_SCHEMA
        or not isinstance(projects, list) or len(projects) != 5
        or not isinstance(scenarios, list) or not scenarios
    ):
        return None
    rows = [
        {key: _text(item.get(key)) for key in ("name", "device", "engine", "surface")}
        for item in projects if isinstance(item, dict)
    ]
    scenario_rows = [
        (_text(item.get("id")), _text(item.get("title")), _text(item.get("file")))
        for item in scenarios if isinstance(item, dict)
    ]
    if len(rows) != 5 or any(not all(row.values()) for row in rows) or len(scenario_rows) != len(scenarios):
        return None
    if any(not all(item) for item in scenario_rows) or len({item[0] for item in scenario_rows}) != len(scenario_rows):
        return None
    if len({row["name"] for row in rows}) != 5 or len({row["device"] for row in rows}) != 5:
        return None
    desktop, mobile = ([row for row in rows if row["surface"] == surface] for surface in ("desktop", "mobile"))
    if len(desktop) != 3 or {row["engine"] for row in desktop} != {"chromium", "firefox", "webkit"}:
        return None
    if len(mobile) != 2 or {row["engine"] for row in mobile} != {"chromium", "webkit"}:
        return None
    canonical = tuple(sorted((title, file) for _, title, file in scenario_rows))
    if len(canonical) != len(set(canonical)):
        return None
    return rows, canonical, _sha256(raw)


def browser_project_names() -> tuple[str, ...]:
    snapshot = _matrix_snapshot()
    return tuple(row["name"] for row in snapshot[0]) if snapshot else ()


def _stats_ok(stats: object, expected: int, *, require_total: bool = False) -> bool:
    return bool(
        isinstance(stats, dict) and _integer(stats.get("expected")) == expected
        and _integer(stats.get("unexpected")) == _integer(stats.get("skipped")) == _integer(stats.get("flaky")) == 0
        and (not require_total or (_integer(stats.get("total")) == expected and stats.get("ok") is True))
    )


def _scenario_matrix(
    records: list[tuple[str, str, str]], projects: tuple[str, ...], canonical: tuple[tuple[str, str], ...],
) -> dict[str, tuple[tuple[str, str], ...]] | None:
    grouped: dict[str, list[tuple[str, str]]] = {project: [] for project in projects}
    for project, title, file in records:
        if project not in grouped or not title or not file:
            return None
        grouped[project].append((title, file))
    signatures = {project: tuple(sorted(values)) for project, values in grouped.items()}
    if not canonical or any(signatures[project] != canonical for project in projects):
        return None
    if any(len(set(signatures[project])) != len(signatures[project]) for project in projects):
        return None
    return signatures


def _json_report(
    payload: object, projects: tuple[str, ...], canonical: tuple[tuple[str, str], ...],
) -> tuple[dict, dict[str, tuple[tuple[str, str], ...]]] | None:
    if not isinstance(payload, dict) or not isinstance(payload.get("config"), dict):
        return None
    configured, suites, stats = payload["config"].get("projects"), payload.get("suites"), payload.get("stats")
    if (
        not isinstance(configured, list) or len(configured) != len(projects) or any(not isinstance(item, dict) for item in configured)
        or tuple(_text(item.get("name")) for item in configured) != projects or not isinstance(suites, list) or not isinstance(stats, dict)
    ):
        return None
    records: list[tuple[str, str, str]] = []

    def visit(suite: object) -> bool:
        if not isinstance(suite, dict) or not isinstance(suite.get("specs", []), list) or not isinstance(suite.get("suites", []), list):
            return False
        for spec in suite.get("specs", []):
            if not isinstance(spec, dict) or spec.get("ok") is not True or not isinstance(spec.get("tests"), list):
                return False
            title, file = _text(spec.get("title")), _text(spec.get("file"))
            if not title or not file or _integer(spec.get("line")) <= 0 or _integer(spec.get("column")) <= 0:
                return False
            for test in spec["tests"]:
                results = test.get("results") if isinstance(test, dict) else None
                if (
                    not isinstance(test, dict) or test.get("expectedStatus") != "passed" or test.get("status") != "expected"
                    or not isinstance(results, list) or not results
                    or any(not isinstance(result, dict) or result.get("status") != "passed" or result.get("errors") for result in results)
                ):
                    return False
                records.append((_text(test.get("projectName")), title, file))
        return all(visit(child) for child in suite.get("suites", []))

    if not all(visit(suite) for suite in suites):
        return None
    matrix = _scenario_matrix(records, projects, canonical)
    return (stats, matrix) if matrix and _stats_ok(stats, len(records)) else None


def _embedded_report(
    html: str, projects: tuple[str, ...], canonical: tuple[tuple[str, str], ...],
) -> tuple[dict, dict[str, tuple[tuple[str, str], ...]]] | None:
    start = html.find(_HTML_REPORT_MARKER)
    end = html.find("</template>", start + len(_HTML_REPORT_MARKER)) if start >= 0 else -1
    if start < 0 or end < 0:
        return None
    try:
        encoded = html[start + len(_HTML_REPORT_MARKER):end].strip()
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(encoded, validate=True))) as archive:
            report = json.loads(archive.read("report.json").decode("utf-8"))
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError, KeyError, zipfile.BadZipFile):
        return None
    if not isinstance(report, dict) or tuple(report.get("projectNames", ())) != projects:
        return None
    files, stats = report.get("files"), report.get("stats")
    if not isinstance(files, list) or not files or not isinstance(stats, dict):
        return None
    records: list[tuple[str, str, str]] = []
    for item in files:
        tests = item.get("tests") if isinstance(item, dict) else None
        if not isinstance(tests, list):
            return None
        for test in tests:
            location, results = (test.get(key) for key in ("location", "results")) if isinstance(test, dict) else (None, None)
            if not isinstance(test, dict) or not isinstance(location, dict) or not isinstance(results, list) or not results:
                return None
            title, file = _text(test.get("title")), _text(location.get("file"))
            result_ok = all(
                isinstance(result, dict) and _integer(result.get("workerIndex")) >= 0 and _timestamp(result.get("startTime"))
                for result in results
            )
            if (
                not _text(test.get("testId")) or not title or not file or _integer(location.get("line")) <= 0
                or _integer(location.get("column")) <= 0 or not result_ok or test.get("outcome") != "expected" or test.get("ok") is not True
            ):
                return None
            records.append((_text(test.get("projectName")), title, file))
    matrix = _scenario_matrix(records, projects, canonical)
    return (stats, matrix) if matrix and _stats_ok(stats, len(records), require_total=True) else None


def _junit_report(
    root: ElementTree.Element, projects: tuple[str, ...], canonical: tuple[tuple[str, str], ...],
) -> tuple[dict[str, tuple[tuple[str, str], ...]], int] | None:
    if root.tag != "testsuites" or any(_integer(root.get(key)) != 0 for key in ("failures", "skipped", "errors")):
        return None
    suites = list(root)
    if not suites or any(suite.tag != "testsuite" for suite in suites):
        return None
    records: list[tuple[str, str, str]] = []
    total = 0
    for suite in suites:
        project = _text(suite.get("hostname"))
        cases = [child for child in suite if child.tag == "testcase"]
        if project not in projects or any(_integer(suite.get(key)) != 0 for key in ("failures", "skipped", "errors")):
            return None
        if _integer(suite.get("tests")) != len(cases) or any(child.tag != "testcase" for child in suite):
            return None
        for case in cases:
            if any(child.tag in {"failure", "error", "skipped"} for child in case):
                return None
            records.append((project, _text(case.get("name")), _text(case.get("classname"))))
        total += len(cases)
    matrix = _scenario_matrix(records, projects, canonical)
    return (matrix, total) if matrix and _integer(root.get("tests")) == total else None


def browser_artifact_snapshot(browser_dir: Path) -> dict | None:
    matrix = _matrix_snapshot()
    if not matrix:
        return None
    project_matrix, canonical, matrix_sha = matrix
    projects = tuple(row["name"] for row in project_matrix)
    json_path, junit_path, html_path = browser_dir / "playwright.json", browser_dir / "junit.xml", browser_dir / "html" / "index.html"
    try:
        json_bytes, junit_bytes, html_bytes = json_path.read_bytes(), junit_path.read_bytes(), html_path.read_bytes()
        json_report = _json_report(json.loads(json_bytes.decode("utf-8")), projects, canonical)
        junit_root = ElementTree.fromstring(junit_bytes)
        html = html_bytes.decode("utf-8")
    except (OSError, UnicodeError, json.JSONDecodeError, ElementTree.ParseError):
        return None
    html_report = _embedded_report(html, projects, canonical)
    junit_report = _junit_report(junit_root, projects, canonical)
    if not json_report or not html_report or not junit_report:
        return None
    json_stats, json_matrix = json_report
    html_stats, html_matrix = html_report
    junit_matrix, testcases = junit_report
    expected = _integer(json_stats.get("expected"))
    if json_matrix != html_matrix or json_matrix != junit_matrix or expected != _integer(html_stats.get("expected")) or testcases != expected:
        return None
    if "<title>Playwright Test Report</title>" not in html or "</html>" not in html:
        return None
    counts = {project: len(json_matrix[project]) for project in projects}
    return {
        "stats": json_stats,
        "projects": [{**row, "tests": counts[row["name"]]} for row in project_matrix],
        "project_matrix": {"path": BROWSER_PROJECT_MATRIX, "schema": BROWSER_PROJECT_MATRIX_SCHEMA, "sha256": matrix_sha},
        "artifacts": {
            "json": {"path": "browser-e2e/playwright.json", "sha256": _sha256(json_bytes), "bytes": len(json_bytes)},
            "junit": {"path": "browser-e2e/junit.xml", "sha256": _sha256(junit_bytes), "bytes": len(junit_bytes), "tests": testcases, "failures": 0, "skipped": 0},
            "html": {"path": "browser-e2e/html/index.html", "sha256": _sha256(html_bytes), "bytes": len(html_bytes)},
        },
    }


__all__ = ["BROWSER_EVIDENCE_NAME", "BROWSER_EVIDENCE_SCHEMA", "BROWSER_PROJECT_MATRIX", "BROWSER_PROJECT_MATRIX_SCHEMA", "browser_artifact_snapshot", "browser_project_names"]
