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
_HTML_MARKER = '<template id="playwrightReportBase64">data:application/zip;base64,'
_HTML_RESULT_KEYS = frozenset({"attachments", "startTime", "workerIndex"})
_HTML_TEST_KEYS = frozenset({"testId", "title", "projectName", "location", "duration", "annotations", "tags", "outcome", "path", "ok", "results"})
_HTML_DETAIL_RESULT_KEYS = frozenset({"duration", "startTime", "retry", "steps", "errors", "status", "attachments", "annotations", "workerIndex"})
_STEP_KEYS = frozenset({"title", "startTime", "duration", "steps", "attachments", "count", "skipped"})
_STEP_LOCATION_KEYS = _STEP_KEYS | {"location", "snippet"}
_JSON_RESULT_KEYS = frozenset({"workerIndex", "parallelIndex", "status", "duration", "errors", "stdout", "stderr", "retry", "startTime", "annotations", "attachments"})


def _need(condition: object) -> None:
    if not condition:
        raise ValueError("invalid browser evidence")


def _integer(value: object) -> int:
    return value if type(value) is int else int(value) if isinstance(value, str) and value.isdecimal() else -1


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _timestamp(value: object) -> bool:
    text = _text(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return "T" in text and parsed.tzinfo is not None and parsed.utcoffset() is not None


def _step_ok(step: object, file: str) -> bool:
    keys = set(step) if isinstance(step, dict) else set()
    location = step.get("location") if isinstance(step, dict) else None
    return bool(keys in {_STEP_KEYS, _STEP_LOCATION_KEYS} and _text(step.get("title")) and _timestamp(step.get("startTime")) and type(step.get("duration")) is int and step["duration"] >= 0 and step.get("attachments") == [] and step.get("count") == 1 and step.get("skipped") is False and _steps(step.get("steps"), file) and (keys == _STEP_KEYS or (isinstance(location, dict) and set(location) == {"file", "line", "column"} and _text(location.get("file")) == file and min(_integer(location.get("line")), _integer(location.get("column"))) > 0 and _text(step.get("snippet")))))


def _steps(value: object, file: str) -> bool:
    return isinstance(value, list) and all(_step_ok(step, file) for step in value)


def _matrix_snapshot():
    try:
        raw = (repo_root() / BROWSER_PROJECT_MATRIX).read_bytes()
        doc = json.loads(raw)
        _need(isinstance(doc, dict) and doc.get("schema") == BROWSER_PROJECT_MATRIX_SCHEMA)
        projects, scenarios = doc.get("projects"), doc.get("scenarios")
        _need(isinstance(projects, list) and len(projects) == 5 and isinstance(scenarios, list) and scenarios)
        rows = [{key: _text(item.get(key)) for key in ("name", "device", "engine", "surface")} for item in projects if isinstance(item, dict)]
        identities = [(_text(item.get("id")), _text(item.get("title")), _text(item.get("file"))) for item in scenarios if isinstance(item, dict)]
        _need(len(rows) == 5 and len(identities) == len(scenarios) and all(all(row.values()) for row in rows))
        _need(all(all(item) for item in identities) and len({item[0] for item in identities}) == len(identities))
        _need(len({row["name"] for row in rows}) == len({row["device"] for row in rows}) == 5)
        desktop = [row for row in rows if row["surface"] == "desktop"]
        mobile = [row for row in rows if row["surface"] == "mobile"]
        _need(len(desktop) == 3 and {row["engine"] for row in desktop} == {"chromium", "firefox", "webkit"})
        _need(len(mobile) == 2 and {row["engine"] for row in mobile} == {"chromium", "webkit"})
        canonical = tuple(sorted((title, file) for _, title, file in identities))
        _need(len(canonical) == len(set(canonical)))
        return rows, canonical, hashlib.sha256(raw).hexdigest()
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return None


def browser_project_names() -> tuple[str, ...]:
    contract = _matrix_snapshot()
    return tuple(row["name"] for row in contract[0]) if contract else ()


def _stats_ok(stats: object, expected: int, *, total: bool = False) -> bool:
    return bool(isinstance(stats, dict) and _integer(stats.get("expected")) == expected and all(_integer(stats.get(key)) == 0 for key in ("unexpected", "skipped", "flaky")) and (not total or (_integer(stats.get("total")) == expected and stats.get("ok") is True)))


def _scenario_matrix(records, projects, canonical):
    grouped = {project: [] for project in projects}
    for project, title, file in records:
        if project not in grouped or not title or not file:
            return None
        grouped[project].append((title, file))
    return grouped if canonical and all(tuple(sorted(grouped[project])) == canonical for project in projects) else None


def _walk(suites):
    for suite in suites:
        _need(isinstance(suite, dict))
        specs, children = suite.get("specs", []), suite.get("suites", [])
        _need(isinstance(specs, list) and isinstance(children, list))
        yield from specs
        yield from _walk(children)


def _json_report(doc, projects, canonical):
    _need(isinstance(doc, dict) and isinstance(doc.get("config"), dict))
    configured, suites, stats = doc["config"].get("projects"), doc.get("suites"), doc.get("stats")
    _need(isinstance(configured, list) and len(configured) == len(projects) and isinstance(suites, list))
    _need(tuple(_text(item.get("name")) for item in configured if isinstance(item, dict)) == projects)
    records = []
    for spec in _walk(suites):
        _need(isinstance(spec, dict) and spec.get("ok") is True and isinstance(spec.get("tests"), list))
        title, file = _text(spec.get("title")), _text(spec.get("file"))
        _need(title and file and min(_integer(spec.get("line")), _integer(spec.get("column"))) > 0)
        for test in spec["tests"]:
            results = test.get("results") if isinstance(test, dict) else None
            _need(isinstance(test, dict) and test.get("expectedStatus") == "passed" and test.get("status") == "expected")
            _need(isinstance(results, list) and len(results) == 1 and isinstance(results[0], dict) and set(results[0]) == _JSON_RESULT_KEYS
                  and all(type(results[0].get(key)) is int and results[0][key] >= 0 for key in ("workerIndex", "parallelIndex", "duration")) and type(results[0].get("retry")) is int and results[0]["retry"] == 0 and results[0].get("status") == "passed" and results[0].get("errors") == [] and all(results[0].get(key) == [] for key in ("stdout", "stderr", "annotations", "attachments")) and _timestamp(results[0].get("startTime")))
            records.append((_text(test.get("projectName")), title, file))
    _need(_scenario_matrix(records, projects, canonical) and _stats_ok(stats, len(records)))
    return stats


def _html_report(html, projects, canonical):
    start = html.find(_HTML_MARKER)
    end = html.find("</template>", start + len(_HTML_MARKER)) if start >= 0 else -1
    _need(start >= 0 and end >= 0)
    encoded = html[start + len(_HTML_MARKER):end].strip()
    records = []
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(encoded, validate=True))) as archive:
        doc = json.loads(archive.read("report.json"))
        _need(isinstance(doc, dict) and tuple(doc.get("projectNames", ())) == projects and isinstance(doc.get("files"), list))
        for item in doc["files"]:
            tests, file_id, file_name = (item.get("tests"), _text(item.get("fileId")), _text(item.get("fileName"))) if isinstance(item, dict) else (None, "", "")
            _need(isinstance(tests, list) and file_id and file_name and _stats_ok(item.get("stats"), len(tests), total=True))
            detail = json.loads(archive.read(f"{file_id}.json"))
            detail_tests = detail.get("tests") if isinstance(detail, dict) else None
            _need(isinstance(detail_tests, list) and detail.get("fileId") == file_id and detail.get("fileName") == file_name and len(detail_tests) == len(tests))
            for test, detailed in zip(tests, detail_tests, strict=True):
                _need(isinstance(test, dict) and isinstance(detailed, dict) and set(test) == set(detailed) == _HTML_TEST_KEYS)
                _need(all(detailed.get(key) == test.get(key) for key in _HTML_TEST_KEYS - {"results"}))
                location, results, detail_results = test["location"], test["results"], detailed["results"]
                _need(isinstance(location, dict) and set(location) == {"file", "line", "column"} and _text(location.get("file")) == file_name and min(_integer(location.get("line")), _integer(location.get("column"))) > 0 and isinstance(results, list) and len(results) == 1 and isinstance(results[0], dict))
                _need(set(results[0]) == _HTML_RESULT_KEYS and results[0].get("attachments") == [] and type(results[0].get("workerIndex")) is int and results[0]["workerIndex"] >= 0 and _timestamp(results[0].get("startTime")))
                _need(isinstance(detail_results, list) and len(detail_results) == 1 and isinstance(detail_results[0], dict) and set(detail_results[0]) == _HTML_DETAIL_RESULT_KEYS and type(detail_results[0].get("duration")) is int and detail_results[0]["duration"] >= 0 and detail_results[0].get("retry") == 0 and detail_results[0].get("status") == "passed" and all(detail_results[0].get(key) == [] for key in ("errors", "attachments", "annotations")) and type(detail_results[0].get("workerIndex")) is int and detail_results[0]["workerIndex"] >= 0 and _timestamp(detail_results[0].get("startTime")) and isinstance(detail_results[0].get("steps"), list) and bool(detail_results[0]["steps"]) and _steps(detail_results[0]["steps"], file_name))
                _need(detail_results[0]["startTime"] == results[0]["startTime"] and detail_results[0]["workerIndex"] == results[0]["workerIndex"] and detail_results[0]["duration"] == detailed["duration"])
                title = _text(test.get("title"))
                _need(_text(test.get("testId")) and title and test.get("outcome") == "expected" and test.get("ok") is True)
                records.append((_text(test.get("projectName")), title, file_name))
    stats = doc.get("stats")
    _need(_scenario_matrix(records, projects, canonical) and _stats_ok(stats, len(records), total=True))
    return stats


def _junit_report(root, projects, canonical) -> int:
    _need(root.tag == "testsuites" and all(_integer(root.get(key)) == 0 for key in ("failures", "skipped", "errors")))
    records = []
    for suite in root:
        project, cases = _text(suite.get("hostname")), list(suite)
        _need(suite.tag == "testsuite" and project in projects and _integer(suite.get("tests")) == len(cases))
        _need(all(_integer(suite.get(key)) == 0 for key in ("failures", "skipped", "errors")))
        _need(all(case.tag == "testcase" for case in cases))
        for case in cases:
            _need(not any(child.tag in {"failure", "error", "skipped"} for child in case))
            records.append((project, _text(case.get("name")), _text(case.get("classname"))))
    _need(_scenario_matrix(records, projects, canonical) and _integer(root.get("tests")) == len(records))
    return len(records)


def browser_artifact_snapshot(browser_dir: Path) -> dict | None:
    contract = _matrix_snapshot()
    if not contract:
        return None
    matrix, canonical, matrix_sha = contract
    projects = tuple(row["name"] for row in matrix)
    paths = browser_dir / "playwright.json", browser_dir / "junit.xml", browser_dir / "html" / "index.html"
    try:
        json_bytes, junit_bytes, html_bytes = (path.read_bytes() for path in paths)
        json_stats = _json_report(json.loads(json_bytes), projects, canonical)
        junit_tests = _junit_report(ElementTree.fromstring(junit_bytes), projects, canonical)
        html = html_bytes.decode()
        html_stats = _html_report(html, projects, canonical)
        expected = _integer(json_stats.get("expected"))
        _need(expected > 0 and _integer(html_stats.get("expected")) == expected == junit_tests)
        _need("<title>Playwright Test Report</title>" in html and "</html>" in html)
    except (OSError, UnicodeError, json.JSONDecodeError, ElementTree.ParseError, zipfile.BadZipFile, KeyError, TypeError, ValueError):
        return None
    artifacts = {name: {"path": rel, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)} for name, rel, raw in zip(("json", "junit", "html"), ("browser-e2e/playwright.json", "browser-e2e/junit.xml", "browser-e2e/html/index.html"), (json_bytes, junit_bytes, html_bytes), strict=True)}
    artifacts["junit"].update(tests=junit_tests, failures=0, skipped=0)
    return {"stats": json_stats, "projects": [{**row, "tests": len(canonical)} for row in matrix], "project_matrix": {"path": BROWSER_PROJECT_MATRIX, "schema": BROWSER_PROJECT_MATRIX_SCHEMA, "sha256": matrix_sha}, "artifacts": artifacts}


__all__ = ["BROWSER_EVIDENCE_NAME", "BROWSER_EVIDENCE_SCHEMA", "BROWSER_PROJECT_MATRIX", "BROWSER_PROJECT_MATRIX_SCHEMA", "browser_artifact_snapshot", "browser_project_names"]
