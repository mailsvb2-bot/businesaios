from __future__ import annotations

import base64
import hashlib
import io
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from scripts.ci.paths import repo_root

BROWSER_EVIDENCE_NAME = "browser-e2e-evidence.json"
BROWSER_EVIDENCE_SCHEMA = "businessaios_browser_e2e.v2"
BROWSER_PROJECT_MATRIX = "frontend/e2e/project-matrix.json"
BROWSER_PROJECT_MATRIX_SCHEMA = "businessaios_browser_project_matrix.v1"
_HTML_REPORT_MARKER = '<template id="playwrightReportBase64">data:application/zip;base64,'


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _count(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _matrix_snapshot() -> tuple[list[dict[str, str]], str] | None:
    try:
        raw = (repo_root() / BROWSER_PROJECT_MATRIX).read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    projects = payload.get("projects") if isinstance(payload, dict) else None
    if payload.get("schema") != BROWSER_PROJECT_MATRIX_SCHEMA or not isinstance(projects, list) or len(projects) != 5:
        return None
    normalized: list[dict[str, str]] = []
    for item in projects:
        if not isinstance(item, dict):
            return None
        row = {key: str(item.get(key) or "").strip() for key in ("name", "device", "engine", "surface")}
        if not all(row.values()) or row["engine"] not in {"chromium", "firefox", "webkit"} or row["surface"] not in {"desktop", "mobile"}:
            return None
        normalized.append(row)
    if len({row["name"] for row in normalized}) != 5 or len({row["device"] for row in normalized}) != 5:
        return None
    desktop = [row for row in normalized if row["surface"] == "desktop"]
    mobile = [row for row in normalized if row["surface"] == "mobile"]
    if len(desktop) != 3 or {row["engine"] for row in desktop} != {"chromium", "firefox", "webkit"}:
        return None
    if len(mobile) != 2 or {row["engine"] for row in mobile} != {"chromium", "webkit"}:
        return None
    return normalized, _sha256(raw)


def browser_project_names() -> tuple[str, ...]:
    snapshot = _matrix_snapshot()
    return tuple(row["name"] for row in snapshot[0]) if snapshot else ()


def _stats_ok(stats: dict, total: int, *, html: bool = False) -> bool:
    return bool(
        _count(stats.get("expected")) == total and _count(stats.get("unexpected")) == 0
        and _count(stats.get("skipped")) == 0 and _count(stats.get("flaky")) == 0
        and (not html or (_count(stats.get("total")) == total and stats.get("ok") is True))
    )


def _matrix_records(records: list[tuple[str, tuple[object, ...]]], project_names: tuple[str, ...]) -> tuple[dict[str, int], dict[str, tuple[tuple[object, ...], ...]]] | None:
    grouped: dict[str, list[tuple[object, ...]]] = {name: [] for name in project_names}
    for project, signature in records:
        if project not in grouped:
            return None
        grouped[project].append(signature)
    signatures = {name: tuple(sorted(values, key=repr)) for name, values in grouped.items()}
    baseline = signatures.get(project_names[0], ()) if project_names else ()
    if not baseline or any(signatures[name] != baseline for name in project_names):
        return None
    return {name: len(signatures[name]) for name in project_names}, signatures


def _json_report(payload: dict, project_names: tuple[str, ...]) -> tuple[dict, dict[str, int], dict[str, tuple[tuple[object, ...], ...]]] | None:
    config, suites, stats = payload.get("config"), payload.get("suites"), payload.get("stats")
    if not isinstance(config, dict) or not isinstance(suites, list) or not isinstance(stats, dict):
        return None
    configured = config.get("projects")
    if not isinstance(configured, list) or tuple(item.get("name") for item in configured if isinstance(item, dict)) != project_names:
        return None
    records: list[tuple[str, tuple[object, ...]]] = []

    def visit(suite: object) -> bool:
        if not isinstance(suite, dict):
            return False
        specs, children = suite.get("specs", []), suite.get("suites", [])
        if not isinstance(specs, list) or not isinstance(children, list):
            return False
        for spec in specs:
            if not isinstance(spec, dict) or spec.get("ok") is not True or not isinstance(spec.get("tests"), list):
                return False
            title, file = str(spec.get("title") or "").strip(), str(spec.get("file") or "").strip()
            line, column = _count(spec.get("line")), _count(spec.get("column"))
            if not title or not file or line <= 0 or column <= 0:
                return False
            signature = (title, file, line, column)
            for test in spec["tests"]:
                results = test.get("results") if isinstance(test, dict) else None
                if not isinstance(results, list) or not results or test.get("expectedStatus") != "passed" or test.get("status") != "expected":
                    return False
                if any(not isinstance(result, dict) or result.get("status") != "passed" or result.get("errors") for result in results):
                    return False
                records.append((str(test.get("projectName") or ""), signature))
        return all(visit(child) for child in children)

    if not all(visit(suite) for suite in suites):
        return None
    matrix = _matrix_records(records, project_names)
    if not matrix or not _stats_ok(stats, len(records)):
        return None
    return stats, *matrix


def _embedded_html_report(html: str, project_names: tuple[str, ...]) -> tuple[dict, dict[str, int], dict[str, tuple[tuple[object, ...], ...]]] | None:
    start = html.find(_HTML_REPORT_MARKER)
    end = html.find("</template>", start + len(_HTML_REPORT_MARKER)) if start >= 0 else -1
    if start < 0 or end < 0:
        return None
    try:
        archive_bytes = base64.b64decode(html[start + len(_HTML_REPORT_MARKER):end].strip(), validate=True)
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            report = json.loads(archive.read("report.json").decode("utf-8"))
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError, KeyError, zipfile.BadZipFile):
        return None
    files, stats = report.get("files"), report.get("stats") if isinstance(report, dict) else (None, None)
    if not isinstance(report, dict) or tuple(report.get("projectNames", ())) != project_names or not isinstance(files, list) or not files or not isinstance(stats, dict):
        return None
    records: list[tuple[str, tuple[object, ...]]] = []
    for item in files:
        tests = item.get("tests") if isinstance(item, dict) else None
        if not isinstance(tests, list):
            return None
        for test in tests:
            location = test.get("location") if isinstance(test, dict) else None
            results = test.get("results") if isinstance(test, dict) else None
            title = str(test.get("title") or "").strip() if isinstance(test, dict) else ""
            file = str(location.get("file") or "").strip() if isinstance(location, dict) else ""
            line, column = _count(location.get("line")), _count(location.get("column")) if isinstance(location, dict) else (-1, -1)
            if (
                not isinstance(test, dict) or not str(test.get("testId") or "").strip() or not title or not file or line <= 0 or column <= 0
                or test.get("outcome") != "expected" or test.get("ok") is not True or not isinstance(results, list) or not results
            ):
                return None
            records.append((str(test.get("projectName") or ""), (title, file, line, column)))
    matrix = _matrix_records(records, project_names)
    if not matrix or not _stats_ok(stats, len(records), html=True):
        return None
    return stats, *matrix


def browser_artifact_snapshot(browser_dir: Path) -> dict | None:
    matrix = _matrix_snapshot()
    if not matrix:
        return None
    project_matrix, matrix_sha = matrix
    project_names = tuple(row["name"] for row in project_matrix)
    json_path, junit_path, html_path = (
        browser_dir / "playwright.json", browser_dir / "junit.xml", browser_dir / "html" / "index.html",
    )
    try:
        json_bytes, junit_bytes, html_bytes = json_path.read_bytes(), junit_path.read_bytes(), html_path.read_bytes()
        payload = json.loads(json_bytes.decode("utf-8"))
        junit_root = ElementTree.fromstring(junit_bytes)
        html = html_bytes.decode("utf-8")
    except (OSError, UnicodeError, json.JSONDecodeError, ElementTree.ParseError):
        return None
    if not isinstance(payload, dict):
        return None
    json_report = _json_report(payload, project_names)
    html_report = _embedded_html_report(html, project_names)
    if not json_report or not html_report or json_report[1:] != html_report[1:]:
        return None
    stats, counts, _ = json_report
    expected = _count(stats.get("expected"))
    testcases = len(junit_root.findall(".//testcase"))
    junit_failures = len(junit_root.findall(".//failure")) + len(junit_root.findall(".//error"))
    junit_skipped = len(junit_root.findall(".//skipped"))
    if testcases != expected or junit_failures or junit_skipped or "<title>Playwright Test Report</title>" not in html or "</html>" not in html:
        return None
    projects = [{**row, "tests": counts[row["name"]]} for row in project_matrix]
    return {
        "stats": stats,
        "projects": projects,
        "project_matrix": {"path": BROWSER_PROJECT_MATRIX, "schema": BROWSER_PROJECT_MATRIX_SCHEMA, "sha256": matrix_sha},
        "artifacts": {
            "json": {"path": "browser-e2e/playwright.json", "sha256": _sha256(json_bytes), "bytes": len(json_bytes)},
            "junit": {
                "path": "browser-e2e/junit.xml", "sha256": _sha256(junit_bytes), "bytes": len(junit_bytes),
                "tests": testcases, "failures": junit_failures, "skipped": junit_skipped,
            },
            "html": {"path": "browser-e2e/html/index.html", "sha256": _sha256(html_bytes), "bytes": len(html_bytes)},
        },
    }


__all__ = [
    "BROWSER_EVIDENCE_NAME", "BROWSER_EVIDENCE_SCHEMA", "BROWSER_PROJECT_MATRIX", "BROWSER_PROJECT_MATRIX_SCHEMA",
    "browser_artifact_snapshot", "browser_project_names",
]
