from __future__ import annotations

import base64
import hashlib
import io
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree

BROWSER_EVIDENCE_NAME = "browser-e2e-evidence.json"
_HTML_REPORT_MARKER = '<template id="playwrightReportBase64">data:application/zip;base64,'


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _count(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _embedded_html_stats(html: str) -> dict | None:
    start = html.find(_HTML_REPORT_MARKER)
    end = html.find("</template>", start + len(_HTML_REPORT_MARKER)) if start >= 0 else -1
    if start < 0 or end < 0:
        return None
    encoded = html[start + len(_HTML_REPORT_MARKER):end].strip()
    try:
        archive_bytes = base64.b64decode(encoded, validate=True)
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            report = json.loads(archive.read("report.json").decode("utf-8"))
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError, KeyError, zipfile.BadZipFile):
        return None
    if not isinstance(report, dict) or report.get("projectNames") != ["chromium"]:
        return None
    files, stats = report.get("files"), report.get("stats")
    if not isinstance(files, list) or not files or not isinstance(stats, dict):
        return None
    tests = sum(len(item.get("tests", [])) for item in files if isinstance(item, dict) and isinstance(item.get("tests"), list))
    return stats if tests > 0 else None


def browser_artifact_snapshot(browser_dir: Path) -> dict | None:
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
    stats = payload.get("stats") if isinstance(payload, dict) else None
    if not isinstance(stats, dict):
        return None
    expected, unexpected, skipped = (_count(stats.get(key)) for key in ("expected", "unexpected", "skipped"))
    testcases = len(junit_root.findall(".//testcase"))
    junit_failures = len(junit_root.findall(".//failure")) + len(junit_root.findall(".//error"))
    junit_skipped = len(junit_root.findall(".//skipped"))
    html_stats = _embedded_html_stats(html)
    html_ok = bool(
        html_stats and _count(html_stats.get("total")) == testcases and _count(html_stats.get("expected")) == expected
        and _count(html_stats.get("unexpected")) == unexpected and _count(html_stats.get("skipped")) == skipped
        and html_stats.get("ok") is True and "<title>Playwright Test Report</title>" in html and "</html>" in html
    )
    if expected <= 0 or unexpected != 0 or skipped != 0 or testcases != expected or junit_failures or junit_skipped or not html_ok:
        return None
    return {
        "stats": stats,
        "artifacts": {
            "json": {"path": "browser-e2e/playwright.json", "sha256": _sha256(json_bytes), "bytes": len(json_bytes)},
            "junit": {
                "path": "browser-e2e/junit.xml", "sha256": _sha256(junit_bytes), "bytes": len(junit_bytes),
                "tests": testcases, "failures": junit_failures, "skipped": junit_skipped,
            },
            "html": {"path": "browser-e2e/html/index.html", "sha256": _sha256(html_bytes), "bytes": len(html_bytes)},
        },
    }


__all__ = ["BROWSER_EVIDENCE_NAME", "browser_artifact_snapshot"]
