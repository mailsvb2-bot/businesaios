from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree

from scripts.ci.paths import coverage_dir, junit_dir, repo_root, reports_dir
from scripts.ci.repository_sources import iter_repository_python_files
from scripts.ci.subprocess_io import CommandOutcome, run_pytest

_MAX_FAILURE_MESSAGE_CHARS = 4000


def _write_coverage_honesty_artifact(
    *,
    coverage_name: str,
    junit_name: str,
    target_args: list[str],
    mark_expression: str,
) -> None:
    coverage_path = coverage_dir() / coverage_name
    coverage_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "artifact": "pytest_coverage_honesty",
        "coverage_artifact": coverage_name,
        "junit_artifact": junit_name,
        "status": "not_collected",
        "coverage_kind": "not_code_coverage",
        "targets": list(target_args),
        "mark_expression": mark_expression,
        "warnings": [
            "pytest gate does not collect coverage.py metrics",
            "do not interpret this artifact as code coverage",
        ],
        "claims_code_coverage": False,
        "claims_production_ready": False,
    }
    coverage_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _diagnostics_stem(junit_name: str) -> str:
    return str(junit_name or "pytest").removesuffix(".xml").replace("/", "-")


def _failure_excerpt(outcome: CommandOutcome) -> str:
    text = "\n".join(part for part in (outcome.stdout, outcome.stderr) if part)
    if not text.strip():
        return "no pytest output captured"
    return text[-_MAX_FAILURE_MESSAGE_CHARS:]


def _write_pytest_diagnostics(
    *,
    junit_name: str,
    target_args: list[str],
    mark_expression: str,
    outcome: CommandOutcome,
) -> None:
    diagnostics_dir = reports_dir() / "pytest"
    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    stem = _diagnostics_stem(junit_name)
    stdout_path = diagnostics_dir / f"{stem}.stdout.txt"
    stderr_path = diagnostics_dir / f"{stem}.stderr.txt"
    json_path = diagnostics_dir / f"{stem}.failure.json"
    stdout_path.write_text(outcome.stdout or "", encoding="utf-8")
    stderr_path.write_text(outcome.stderr or "", encoding="utf-8")
    payload = {
        "artifact": "pytest_failure_diagnostics",
        "junit_artifact": junit_name,
        "targets": list(target_args),
        "mark_expression": mark_expression,
        "returncode": outcome.returncode,
        "stdout_artifact": stdout_path.relative_to(reports_dir()).as_posix(),
        "stderr_artifact": stderr_path.relative_to(reports_dir()).as_posix(),
        "failure_excerpt": _failure_excerpt(outcome),
        "claims_production_ready": False,
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def run_pytest_with_report(
    *,
    target_args: list[str],
    mark_expression: str,
    junit_name: str,
    coverage_name: str,
    timeout: float | None = None,
) -> tuple[bool, str]:
    junit_path = junit_dir() / junit_name
    args = [
        "-m",
        "pytest",
        "-q",
        *target_args,
        "-m",
        mark_expression,
        "--junitxml",
        str(junit_path),
    ]
    outcome = run_pytest(args, timeout=timeout)
    _write_coverage_honesty_artifact(
        coverage_name=coverage_name,
        junit_name=junit_name,
        target_args=target_args,
        mark_expression=mark_expression,
    )
    if outcome.returncode != 0:
        _write_pytest_diagnostics(
            junit_name=junit_name,
            target_args=target_args,
            mark_expression=mark_expression,
            outcome=outcome,
        )
        excerpt = _failure_excerpt(outcome)
        if outcome.returncode == 124:
            return (
                False,
                f"pytest timed out for targets={target_args} "
                f"mark={mark_expression}\n{excerpt}",
            )
        return (
            False,
            f"pytest failed for targets={target_args} "
            f"mark={mark_expression}\n{excerpt}",
        )
    return True, "pytest gate passed; code coverage not collected"


def _discover_test_files(target_args: list[str]) -> tuple[Path, ...]:
    root = repo_root()
    files: set[Path] = set()
    for target in target_args:
        path = (root / target).resolve()
        if path.is_file() and path.name.startswith("test_") and path.suffix == ".py":
            files.add(path)
            continue
        if path.is_dir():
            files.update(
                candidate
                for candidate in iter_repository_python_files(path)
                if candidate.name.startswith("test_")
            )
    return tuple(sorted(files))


def _build_test_shards(
    files: tuple[Path, ...],
    *,
    max_files: int,
    max_source_bytes: int,
) -> tuple[tuple[Path, ...], ...]:
    if max_files <= 0 or max_source_bytes <= 0:
        raise ValueError("pytest shard bounds must be positive")
    shards: list[tuple[Path, ...]] = []
    current: list[Path] = []
    current_bytes = 0
    for path in files:
        size = path.stat(follow_symlinks=False).st_size
        would_overflow = bool(current) and (
            len(current) >= max_files or current_bytes + size > max_source_bytes
        )
        if would_overflow:
            shards.append(tuple(current))
            current = []
            current_bytes = 0
        current.append(path)
        current_bytes += size
    if current:
        shards.append(tuple(current))
    return tuple(shards)


def _aggregate_junit_files(
    *,
    shard_paths: list[Path],
    output_path: Path,
) -> None:
    suites = ElementTree.Element("testsuites")
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    total_time = 0.0
    for shard_path in shard_paths:
        if not shard_path.exists():
            continue
        shard_root = ElementTree.parse(shard_path).getroot()
        shard_suites = (
            list(shard_root) if shard_root.tag == "testsuites" else [shard_root]
        )
        for suite in shard_suites:
            suites.append(suite)
            for key in totals:
                totals[key] += int(suite.attrib.get(key, "0") or 0)
            total_time += float(suite.attrib.get("time", "0") or 0)
    for key, value in totals.items():
        suites.set(key, str(value))
    suites.set("time", f"{total_time:.6f}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ElementTree.ElementTree(suites).write(
        output_path,
        encoding="utf-8",
        xml_declaration=True,
    )


def run_pytest_sharded_with_report(
    *,
    target_args: list[str],
    mark_expression: str,
    junit_name: str,
    coverage_name: str,
    timeout_per_shard: float | None = None,
    max_files_per_shard: int = 40,
    max_source_bytes_per_shard: int = 1_500_000,
) -> tuple[bool, str]:
    files = _discover_test_files(target_args)
    if not files:
        return run_pytest_with_report(
            target_args=target_args,
            mark_expression=mark_expression,
            junit_name=junit_name,
            coverage_name=coverage_name,
            timeout=timeout_per_shard,
        )
    shards = _build_test_shards(
        files,
        max_files=max_files_per_shard,
        max_source_bytes=max_source_bytes_per_shard,
    )
    shard_junit_paths: list[Path] = []
    failures: list[str] = []
    root = repo_root()
    stem = _diagnostics_stem(junit_name)
    coverage_stem = str(coverage_name).removesuffix(".xml")
    for index, shard in enumerate(shards, start=1):
        shard_junit_name = f"{stem}-shard-{index:03d}.xml"
        shard_coverage_name = f"{coverage_stem}-shard-{index:03d}.xml"
        relative_targets = [path.relative_to(root).as_posix() for path in shard]
        ok, message = run_pytest_with_report(
            target_args=relative_targets,
            mark_expression=mark_expression,
            junit_name=shard_junit_name,
            coverage_name=shard_coverage_name,
            timeout=timeout_per_shard,
        )
        shard_junit_paths.append(junit_dir() / shard_junit_name)
        if not ok:
            failures.append(f"shard {index}/{len(shards)}: {message}")
    _aggregate_junit_files(
        shard_paths=shard_junit_paths,
        output_path=junit_dir() / junit_name,
    )
    _write_coverage_honesty_artifact(
        coverage_name=coverage_name,
        junit_name=junit_name,
        target_args=target_args,
        mark_expression=mark_expression,
    )
    if failures:
        return False, "\n".join(failures)
    return (
        True,
        f"pytest sharded gate passed: {len(files)} files in {len(shards)} shards",
    )


__all__ = [
    "run_pytest_sharded_with_report",
    "run_pytest_with_report",
]
