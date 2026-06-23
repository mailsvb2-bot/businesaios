from __future__ import annotations

import json
import os
import py_compile
from xml.sax.saxutils import escape

from scripts.ci import targeted_domain_ci as targeted
from scripts.ci.paths import coverage_dir, junit_dir
from scripts.ci.subprocess_io import run_pytest


def _chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _write_coverage_honesty_artifact(*, coverage_name: str, junit_names: list[str], target_args: list[str], mark_expression: str) -> None:
    coverage_path = coverage_dir() / coverage_name
    coverage_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "artifact": "pytest_coverage_honesty",
        "coverage_artifact": coverage_name,
        "junit_artifacts": list(junit_names),
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
    coverage_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _write_summary_junit(*, junit_name: str, message: str) -> None:
    junit_path = junit_dir() / junit_name
    junit_path.parent.mkdir(parents=True, exist_ok=True)
    junit_path.write_text(
        '<testsuite name="ci-targeted-domain" tests="1" failures="0" skipped="0">\n'
        f'  <testcase classname="ci" name="targeted-domain-tests"><system-out>{escape(message)}</system-out></testcase>\n'
        '</testsuite>\n',
        encoding="utf-8",
    )


def run() -> tuple[bool, str]:
    base = os.environ.get("TARGETED_CI_BASE", "origin/main")
    changed = targeted.changed_files(base)
    changed_py = [path for path in changed if path.endswith(".py") and (targeted.ROOT / path).is_file()]
    print(f"[targeted-ci] changed={len(changed)} changed_py={len(changed_py)}")

    for path in changed_py:
        py_compile.compile(str(targeted.ROOT / path), doraise=True)

    domains = targeted.touched_domains(changed)
    tests = targeted.matching_tests(domains)
    print(f"[targeted-ci] domains={domains}")
    print(f"[targeted-ci] tests={len(tests)}")
    for test in tests[:200]:
        print(f"[targeted-ci] test={test}")

    if not tests:
        return True, "targeted-domain checks passed: changed Python compiled; no matching domain tests"

    mark_expression = "not slow and not integration and not gate"
    chunk_size = max(1, int(os.environ.get("TARGETED_DOMAIN_CHUNK_SIZE", "40")))
    chunks = _chunks(tests, chunk_size)
    collected_chunks = 0
    empty_chunks = 0
    junit_names: list[str] = []

    for index, chunk in enumerate(chunks, 1):
        junit_name = f"targeted-domain-{index:03d}.xml"
        junit_names.append(junit_name)
        junit_path = junit_dir() / junit_name
        args = [
            "-m",
            "pytest",
            "-q",
            *chunk,
            "-m",
            mark_expression,
            "--junitxml",
            str(junit_path),
        ]
        outcome = run_pytest(args, timeout=300)
        if outcome.returncode == 0:
            collected_chunks += 1
            continue
        if outcome.returncode == 5:
            empty_chunks += 1
            continue
        text = "\n".join(part for part in (outcome.stdout, outcome.stderr) if part)
        return False, (
            f"targeted-domain pytest chunk {index}/{len(chunks)} failed "
            f"for {len(chunk)} test file(s), returncode={outcome.returncode}\n"
            f"{text[-4000:]}"
        )

    if collected_chunks == 0:
        return False, (
            f"targeted-domain selected {len(tests)} test file(s), "
            f"but pytest collected no runnable tests after mark filtering"
        )

    message = (
        f"targeted-domain checks passed: {len(tests)} test file(s), "
        f"chunks={len(chunks)}, collected_chunks={collected_chunks}, empty_chunks={empty_chunks}"
    )
    _write_summary_junit(junit_name="targeted-domain.xml", message=message)
    _write_coverage_honesty_artifact(
        coverage_name="targeted-domain-coverage.json",
        junit_names=["targeted-domain.xml", *junit_names],
        target_args=tests,
        mark_expression=mark_expression,
    )
    return True, message
