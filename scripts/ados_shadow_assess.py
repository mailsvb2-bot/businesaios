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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / ".ados-shadow"


def git(*args: str, text: bool = True) -> str | bytes:
    completed = subprocess.run(
        ["git", *args], cwd=ROOT, check=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=text,
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

        completed = subprocess.run(
            command, cwd=ROOT, check=False,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            sys.stderr.write(completed.stderr)
            sys.stderr.write(completed.stdout)
            raise RuntimeError(f"ADOS did not emit valid JSON (rc={completed.returncode}): {exc}") from exc

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
