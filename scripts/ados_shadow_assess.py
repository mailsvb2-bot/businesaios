#!/usr/bin/env python3
"""Run an ADOS MERGE assessment as a non-blocking shadow verdict.

A valid ADOS assessment always exits 0 from this wrapper, even when ADOS says
that the change WOULD_BLOCK in a strict lane. Infrastructure/JSON failures are
kept distinct and return 2 so the advisory workflow itself can be debugged.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / ".ados-shadow"
CANONICAL_PYTHON_LOCK = ROOT / "requirements.lock.txt"
ADOS_PYTHON_LOCK_ALIAS = ROOT / "requirements.lock"


@contextmanager
def ados_lockfile_compatibility() -> Iterator[None]:
    """Expose the canonical BusinessAIOS lock under ADOS 0.6.0's fixed name.

    ADOS 0.6.0 recognizes ``requirements.lock`` but BusinessAIOS canonically
    owns ``requirements.lock.txt``.  A temporary hardlink preserves one set of
    bytes and one source of truth; it is never committed and is always removed.
    """
    canonical = CANONICAL_PYTHON_LOCK
    alias = ADOS_PYTHON_LOCK_ALIAS
    if not canonical.is_file() or canonical.is_symlink():
        raise RuntimeError(f"canonical Python lock is missing/unsafe: {canonical}")
    if alias.exists() or alias.is_symlink():
        raise RuntimeError(f"ADOS compatibility lock path already exists: {alias}")
    os.link(canonical, alias)
    try:
        if not os.path.samefile(canonical, alias):
            raise RuntimeError("ADOS compatibility lock is not a hardlink to the canonical lock")
        yield
    finally:
        alias.unlink(missing_ok=True)


def validate_assessment_payload(payload: object, *, returncode: int) -> dict:
    """Accept valid advisory assessments and reject controller/infrastructure errors."""
    if not isinstance(payload, dict):
        raise RuntimeError("ADOS assessment payload must be a JSON object")
    if payload.get("error"):
        raise RuntimeError(f"ADOS controller error: {payload['error']}")
    if returncode not in {0, 2, 3}:
        raise RuntimeError(f"ADOS returned unexpected exit code {returncode}")
    required = {
        "task": dict,
        "results": list,
        "blocking_failures": int,
        "unknown_gates": int,
        "release_blockers": int,
    }
    for key, expected in required.items():
        value = payload.get(key)
        if type(value) is not expected:
            raise RuntimeError(f"ADOS assessment field {key!r} must be {expected.__name__}")
    for key in ("blocking_failures", "unknown_gates", "release_blockers"):
        if payload[key] < 0:
            raise RuntimeError(f"ADOS assessment field {key!r} cannot be negative")
    for index, item in enumerate(payload["results"]):
        if not isinstance(item, dict):
            raise RuntimeError(f"ADOS result #{index} must be an object")
        for key in ("gate", "status", "reason"):
            if not isinstance(item.get(key), str) or not item[key]:
                raise RuntimeError(f"ADOS result #{index} has invalid {key!r}")
    return payload


def git(*args: str, text: bool = True) -> str | bytes:
    completed = subprocess.run(
        ["git", *args], cwd=ROOT, check=True,
        capture_output=True, text=text,
    )
    return completed.stdout


def resolve_commit(value: str | None, fallback: str) -> str:
    candidate = (value or "").strip() or fallback
    return str(git("rev-parse", "--verify", f"{candidate}^{{commit}}")).strip()


def resolve_base(value: str | None) -> str:
    if value and value.strip():
        return resolve_commit(value, value)
    try:
        return str(git("merge-base", "origin/main", "HEAD")).strip()
    except subprocess.CalledProcessError:
        return resolve_commit(None, "HEAD^")


def changed_paths(base: str, head: str) -> tuple[list[str], list[str]]:
    raw = git("diff", "--name-status", "-z", "-M", f"{base}...{head}", text=False)
    parts = raw.split(b"\0")
    if parts and parts[-1] == b"":
        parts.pop()
    changed: list[str] = []
    deleted: list[str] = []
    i = 0
    while i < len(parts):
        status = parts[i].decode("utf-8", "surrogateescape")
        i += 1
        code = status[:1]
        if code in {"R", "C"}:
            if i + 1 >= len(parts):
                raise ValueError(f"malformed git diff rename/copy record: {status!r}")
            old = parts[i].decode("utf-8", "surrogateescape")
            new = parts[i + 1].decode("utf-8", "surrogateescape")
            i += 2
            changed.append(new)
            if code == "R":
                deleted.append(old)
            continue
        if i >= len(parts):
            raise ValueError(f"malformed git diff record: {status!r}")
        path = parts[i].decode("utf-8", "surrogateescape")
        i += 1
        if code == "D":
            deleted.append(path)
        else:
            changed.append(path)
    return sorted(dict.fromkeys(changed)), sorted(dict.fromkeys(deleted))


def summary_markdown(payload: dict, *, base: str, head: str, changed: list[str], deleted: list[str]) -> str:
    task = payload.get("task") or {}
    results = payload.get("results") or []
    blockers = int(payload.get("release_blockers") or 0)
    verdict = "WOULD_BLOCK" if blockers else "WOULD_ALLOW"
    lines = [
        "## ADOS shadow assessment",
        "",
        "> Advisory only. This workflow is **not** a required merge/release gate.",
        "",
        f"- Verdict: **{verdict}**",
        "- Lane simulated: `MERGE`",
        f"- Risk: `{task.get('risk', 'UNKNOWN')}`",
        f"- Base: `{base}`",
        f"- Head: `{head}`",
        f"- Changed paths: `{len(changed)}`",
        f"- Deleted paths: `{len(deleted)}`",
        f"- Strict-lane blockers/unknowns: `{blockers}`",
        "",
        "| Gate | Status | Reason |",
        "|---|---|---|",
    ]
    for item in results:
        gate = str(item.get("gate", "?")).replace("|", "\\|")
        status = str(item.get("status", "?")).replace("|", "\\|")
        reason = str(item.get("reason", "")).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| `{gate}` | **{status}** | {reason} |")
    lines.extend([
        "",
        "`WOULD_BLOCK` is information in Phase 1, not a merge failure. UNKNOWN is preserved rather than converted into a fake PASS.",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ados-bin", required=True)
    parser.add_argument("--repository", default="mailsvb2-bot/businesaios")
    parser.add_argument("--base-sha", default="")
    parser.add_argument("--head-sha", default="")
    parser.add_argument("--goal", default="BusinessAIOS pull request shadow assessment")
    args = parser.parse_args()

    try:
        base = resolve_base(args.base_sha)
        head = resolve_commit(args.head_sha, "HEAD")
        changed, deleted = changed_paths(base, head)
        command = [
            args.ados_bin, "assess", "--root", str(ROOT),
            "--task", f"shadow-{head[:12]}",
            "--repository", args.repository,
            "--goal", args.goal,
            "--lane", "MERGE",
        ]
        for path in changed:
            command.extend(["--file", path])
        for path in deleted:
            command.extend(["--deleted-file", path])

        with ados_lockfile_compatibility():
            completed = subprocess.run(
                command, cwd=ROOT, check=False,
                capture_output=True, text=True,
            )
        try:
            decoded = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            sys.stderr.write(completed.stderr)
            sys.stderr.write(completed.stdout)
            raise RuntimeError(f"ADOS did not emit valid JSON (rc={completed.returncode}): {exc}") from exc
        payload = validate_assessment_payload(decoded, returncode=completed.returncode)

        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / "assessment.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        summary = summary_markdown(payload, base=base, head=head, changed=changed, deleted=deleted)
        (OUT_DIR / "summary.md").write_text(summary, encoding="utf-8")
        print(summary)
        github_summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if github_summary:
            with open(github_summary, "a", encoding="utf-8") as handle:
                handle.write(summary)
        if completed.stderr:
            sys.stderr.write(completed.stderr)
        return 0
    except Exception as exc:
        print(f"ADOS shadow infrastructure failure: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
