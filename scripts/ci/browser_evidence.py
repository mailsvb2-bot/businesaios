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
    if not isinstance(payload, dict) or payload.get("schema") != BROWSER_PROJECT_MATRIX_SCHEMA or not isinstance(projects, list) or len(projects) != 5:
        return None
    rows = [
        {key: str(item.get(key) or "").strip() for key in ("name", "device", "engine", "surface")}
        for item in projects if isinstance(item, dict)
    ]
    if len(rows) != 5 or any(not all(row.values()) for row in rows):
        return None
    if len({row["name"] for row in rows}) != 5 or len({row["device"] for row in rows}) != 5:
        return None
    desktop, mobile = ([row for row in rows if row["surface"] == surface] for surface in ("desktop", "mobile"))
    if len(desktop) != 3 or {row["engine"] for row in desktop} != {"chromium", "firefox", "webkit"}:
        return None
    if len(mobile) != 2 or {row["engine"] for row in mobile} != {"chromium", "webkit"}:
        return None
    return rows, _sha256(raw)


def browser_project_names() -> tuple[str, ...]:
    snapshot = _matrix_snapshot()
    return tuple(row["name"] for row in snapshot[0]) if snapshot else ()


def _stats_ok(stats: object, expected: int, *, require_total: bool = False) -> bool:
    return bool(
        isinstance(stats, dict) and _count(stats.get("expected")) == expected
        and _count(stats.get("unexpected")) == _count(stats.get("skipped")) == _count(stats.get("flaky")) == 0
        and (not require_total or (_count(stats.get("total")) == expected and stats.get("ok") is True))
    )


def _json_stats(payload: object, project_names: tuple[str, ...]) -> dict | None:
    if not isinstance(payload, dict) or not isinstance(payload.get("config"), dict):
        return None
    projects, stats = payload["config"].get("projects"), payload.get("stats")
    if not isinstance(projects, list) or len(projects) != len(project_names) or any(not isinstance(item, dict) for item in projects):
        return None
    if tuple(item.get("name") for item in projects) != project_names or not isinstance(stats, dict):
        return None
    expected = _count(stats.get("expected"))
    return stats if expected > 0 and _stats_ok(stats, expected) else None


def _embedded_report(html: str, project_names: tuple[str, ...]) -> tuple[dict, dict[str, int]] | None:
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
    if not isinstance(report, dict) or tuple(report.get("projectNames", ())) != project_names:
        return None
    files, stats = report.get("files"), report.get("stats")
    if not isinstance(files, list) or not files or not isinstance(stats, dict):
        return None
    grouped: dict[str, list[tuple[object, ...]]] = {name: [] for name in project_names}
    for item in files:
        tests = item.get("tests") if isinstance(item, dict) else None
        if not isinstance(tests, list):
            return None
        for test in tests:
            location, results = (test.get(key) for key in ("location", "results")) if isinstance(test, dict) else (None, None)
            if not isinstance(test, dict) or not isinstance(location, dict) or not isinstance(results, list) or not results:
                return None
            project = str(test.get("projectName") or "")
            signature = (str(test.get("title") or "").strip(), str(location.get("file") or "").strip(), _count(location.get("line")), _count(location.get("column")))
            if project not in grouped or not str(test.get("testId") or "").strip() or not all(signature) or test.get("outcome") != "expected" or test.get("ok") is not True:
                return None
            grouped[project].append(signature)
    signatures = {name: tuple(sorted(values, key=repr)) for name, values in grouped.items()}
    baseline = signatures[project_names[0]] if project_names else ()
    total = sum(len(values) for values in signatures.values())
    if not baseline or any(signatures[name] != baseline for name in project_names) or not _stats_ok(stats, total, require_total=True):
        return None
    return stats, {name: len(signatures[name]) for name in project_names}


def browser_artifact_snapshot(browser_dir: Path) -> dict | None:
    matrix = _matrix_snapshot()
    if not matrix:
        return None
    project_matrix, matrix_sha = matrix
    project_names = tuple(row["name"] for row in project_matrix)
    json_path, junit_path, html_path = browser_dir / "playwright.json", browser_dir / "junit.xml", browser_dir / "html" / "index.html"
    try:
        json_bytes, junit_bytes, html_bytes = json_path.read_bytes(), junit_path.read_bytes(), html_path.read_bytes()
        json_stats = _json_stats(json.loads(json_bytes.decode("utf-8")), project_names)
        junit_root = ElementTree.fromstring(junit_bytes)
        html = html_bytes.decode("utf-8")
    except (OSError, UnicodeError, json.JSONDecodeError, ElementTree.ParseError):
        return None
    html_report = _embedded_report(html, project_names)
    if not json_stats or not html_report:
        return None
    html_stats, counts = html_report
    expected = _count(json_stats.get("expected"))
    testcases = len(junit_root.findall(".//testcase"))
    failures = len(junit_root.findall(".//failure")) + len(junit_root.findall(".//error"))
    skipped = len(junit_root.findall(".//skipped"))
    if expected != _count(html_stats.get("expected")) or testcases != expected or failures or skipped:
        return None
    if "<title>Playwright Test Report</title>" not in html or "</html>" not in html:
        return None
    return {
        "stats": json_stats,
        "projects": [{**row, "tests": counts[row["name"]]} for row in project_matrix],
        "project_matrix": {"path": BROWSER_PROJECT_MATRIX, "schema": BROWSER_PROJECT_MATRIX_SCHEMA, "sha256": matrix_sha},
        "artifacts": {
            "json": {"path": "browser-e2e/playwright.json", "sha256": _sha256(json_bytes), "bytes": len(json_bytes)},
            "junit": {"path": "browser-e2e/junit.xml", "sha256": _sha256(junit_bytes), "bytes": len(junit_bytes), "tests": testcases, "failures": failures, "skipped": skipped},
            "html": {"path": "browser-e2e/html/index.html", "sha256": _sha256(html_bytes), "bytes": len(html_bytes)},
        },
    }


__all__ = ["BROWSER_EVIDENCE_NAME", "BROWSER_EVIDENCE_SCHEMA", "BROWSER_PROJECT_MATRIX", "BROWSER_PROJECT_MATRIX_SCHEMA", "browser_artifact_snapshot", "browser_project_names"]
