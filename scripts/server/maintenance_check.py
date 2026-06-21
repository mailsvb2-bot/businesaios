from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.ci.paths import repo_root as ci_repo_root
from scripts.ci.subprocess_io import run_command


REPORT_DIR_DEFAULT = Path(os.getenv("BUSINESAIOS_TEST_REPORT_DIR", "/tmp/businesaios-pytest-runs"))
CACHE_DIR_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".hypothesis"}
ARTIFACT_SUFFIXES = (
    ".pyc",
    ".pyo",
    ".lock",
    ".sqlite",
    ".sqlite3",
    ".sqlite-wal",
    ".sqlite-shm",
    ".sqlite3-wal",
    ".sqlite3-shm",
    ".db",
    ".db-wal",
    ".db-shm",
    ".zip",
)
GENERATED_FILE_SUFFIXES = (".jsonl", ".log", ".tmp", ".bak", ".bak2")
NEVER_DESCEND = {".git", ".venv", "venv", "node_modules"}
LOCAL_RUNNER_DIR_NAMES = {"actions-runner-businesaios"}
GENERATED_DIR_PREFIXES = (
    Path(".runtime"),
    Path("runtime/data/reports"),
    Path("runtime/data/security"),
    Path("artifacts/ci"),
    Path("security"),
    Path("data/config"),
)


class Tee:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("w", encoding="utf-8")

    def write(self, text: str) -> None:
        sys.stdout.write(text)
        sys.stdout.flush()
        self._file.write(text)
        self._file.flush()

    def close(self) -> None:
        self._file.close()


def repo_root() -> Path:
    return ci_repo_root().resolve()


def relpath(root: Path, path: Path) -> Path:
    return path.resolve().relative_to(root)


def git_tracked_files(root: Path) -> set[Path]:
    result = run_command(["git", "ls-files", "-z"], cwd=root, echo_output=False)
    if result.returncode != 0:
        raise SystemExit(result.stderr)
    return {Path(item) for item in result.stdout.split("\0") if item}


def has_tracked_child(rel_dir: Path, tracked: set[Path]) -> bool:
    prefix = str(rel_dir).rstrip("/") + "/"
    return any(str(item).startswith(prefix) for item in tracked)


def under_any(path: Path, prefixes: Iterable[Path]) -> bool:
    text = str(path)
    return any(text == str(prefix) or text.startswith(str(prefix).rstrip("/") + "/") for prefix in prefixes)


def remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)


def clean_local_artifacts(root: Path, *, dry_run: bool = False, deep_clean: bool = False) -> dict[str, object]:
    tracked = git_tracked_files(root)
    removed: list[str] = []
    skipped_tracked: list[str] = []

    for current, dirnames, filenames in os.walk(root):
        current_path = Path(current)
        rel_current = relpath(root, current_path) if current_path != root else Path(".")

        dirnames[:] = [name for name in dirnames if name not in NEVER_DESCEND]

        for dirname in list(dirnames):
            path = current_path / dirname
            rel = relpath(root, path)
            should_remove = (
                dirname in CACHE_DIR_NAMES
                or (rel_current == Path(".") and dirname in LOCAL_RUNNER_DIR_NAMES)
                or (dirname == "target" and "rust" in rel.parts)
            )
            if deep_clean and dirname == "target":
                should_remove = True
            if not should_remove:
                continue
            if has_tracked_child(rel, tracked):
                skipped_tracked.append(str(rel))
                continue
            removed.append(str(rel))
            if not dry_run:
                remove_path(path)
            dirnames.remove(dirname)

        for filename in filenames:
            path = current_path / filename
            rel = relpath(root, path)
            if rel in tracked:
                continue
            suffix_match = filename.endswith(ARTIFACT_SUFFIXES)
            generated_dir = under_any(rel, GENERATED_DIR_PREFIXES)
            generated_file = generated_dir and filename.endswith(GENERATED_FILE_SUFFIXES)
            empty_generated = path.exists() and path.is_file() and path.stat().st_size == 0 and generated_dir
            repo_report = under_any(rel, (Path("runtime/data/reports"),))
            should_remove = suffix_match or generated_file or empty_generated or repo_report
            if not should_remove:
                continue
            removed.append(str(rel))
            if not dry_run:
                remove_path(path)

    return {
        "removed_n": len(removed),
        "removed": removed,
        "skipped_tracked_n": len(skipped_tracked),
        "skipped_tracked": skipped_tracked,
        "dry_run": dry_run,
        "deep_clean": deep_clean,
    }


def build_isolated_pytest_env(report_dir: Path, stamp: str) -> dict[str, str]:
    runtime_root = (report_dir / "runtime-data" / stamp).resolve()
    data_dir = runtime_root / "data"
    tenancy_dir = runtime_root / "tenancy"
    security_dir = runtime_root / "security"
    for path in (data_dir, tenancy_dir, security_dir):
        path.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.pop("PYTEST_DISABLE_PLUGIN_AUTOLOAD", None)
    env.update(
        {
            "DATA_DIR": str(data_dir),
            "BUSINESAIOS_DATA_DIR": str(data_dir),
            "BAIOS_DATA_DIR": str(data_dir),
            "BUSINESAIOS_TENANCY_DATA_DIR": str(tenancy_dir),
            "BUSINESAIOS_TENANT_REGISTRY_PATH": str(tenancy_dir / "tenant_registry.json"),
            "BUSINESAIOS_TENANT_POLICY_STORE_PATH": str(tenancy_dir / "tenant_policies.json"),
            "BUSINESAIOS_API_KEY_STORE_PATH": str(security_dir / "api_keys.json"),
            "BUSINESAIOS_API_IDEMPOTENCY_PATH": str(data_dir / "api" / "api_idempotency.sqlite3"),
            "API_IDEMPOTENCY_PATH": str(data_dir / "api" / "api_idempotency.sqlite3"),
            "WORLD_MODEL_DIR": str(data_dir / "world_models"),
            "SECURITY_AUDIT_PATH": str(security_dir / "security_audit.jsonl"),
            "WEB_SECURITY_AUDIT_PATH": str(security_dir / "web_security_audit.jsonl"),
            "CONTROL_PLANE_AUDIT_PATH": str(security_dir / "control_plane_audit.jsonl"),
        }
    )
    return env


def run_pytest_count(root: Path, report_dir: Path, pytest_args: list[str]) -> tuple[int, Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = report_dir / f"{stamp}.json"
    log_path = report_dir / f"{stamp}.log"
    script = root / "scripts" / "ci" / "count_pytest_errors.py"
    if not script.exists():
        raise SystemExit(f"Missing pytest counter: {script}")

    cmd = [sys.executable, str(script), "--json", str(json_path), "--", *pytest_args]
    tee = Tee(log_path)
    tee.write("$ " + " ".join(cmd) + "\n")
    process = subprocess.Popen(
        cmd,
        cwd=str(root),
        env=build_isolated_pytest_env(report_dir, stamp),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        tee.write(line)
    rc = int(process.wait())
    tee.write(f"\n[maintenance] pytest-count exit_code={rc}\n")
    tee.close()
    return rc, json_path, log_path


def load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def classify_failed_item(item: str) -> str:
    text = item.lower()
    if "sqlite" in text or "storage" in text or "analytics" in text:
        return "storage/sqlite/analytics"
    if "release" in text or "clean" in text or "manifest" in text or "artifact" in text or "pycache" in text:
        return "release/clean/artifacts"
    if ".arch." in text or "canon" in text or "surface" in text or "owner" in text or "lock" in text:
        return "architecture/canon-locks"
    if "effect" in text or "executor" in text or "outbox" in text or "yookassa" in text or "telegram" in text:
        return "runtime/effects/messaging"
    if "decision" in text or "gateway" in text or "ring" in text:
        return "decision/ring"
    if "tenant" in text:
        return "tenant/governance"
    return "other"


def print_report_summary(path: Path, *, max_items: int = 20) -> None:
    data = load_json(path)
    print("\n=== PYTEST SUMMARY ===")
    print(f"report:         {path}")
    print(f"total:          {data.get('total')}")
    print(f"passed:         {data.get('passed')}")
    print(f"failures:       {data.get('failures')}")
    print(f"errors:         {data.get('errors')}")
    print(f"skipped:        {data.get('skipped')}")
    print(f"problems:       {data.get('problem_count')}")
    print(f"success:        {data.get('success')}")

    failed_items = list(data.get("failed_items") or [])
    error_items = list(data.get("error_items") or [])
    all_items = failed_items + error_items
    groups = Counter(classify_failed_item(str(item)) for item in all_items)
    if groups:
        print("\n=== PROBLEM GROUPS ===")
        for group, count in groups.most_common():
            print(f"{count:>4}  {group}")

    if all_items:
        by_group: dict[str, list[str]] = defaultdict(list)
        for item in all_items:
            by_group[classify_failed_item(str(item))].append(str(item))
        print("\n=== FIRST FAILED ITEMS BY GROUP ===")
        shown = 0
        for group, items in sorted(by_group.items()):
            print(f"[{group}]")
            for item in items[:5]:
                print(f"  - {item}")
                shown += 1
                if shown >= max_items:
                    return


def print_last_reports(report_dir: Path, *, limit: int) -> None:
    files = sorted(report_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)[-limit:]
    if not files:
        print("\nNo saved reports yet.")
        return
    print(f"\n=== LAST {len(files)} REPORTS ===")
    for path in files:
        data = load_json(path)
        print(
            f"{path.name}: total={data.get('total')} "
            f"passed={data.get('passed')} failures={data.get('failures')} "
            f"errors={data.get('errors')} problems={data.get('problem_count')}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Server maintenance wrapper for BusinessAIOS pytest debt checks.")
    parser.add_argument("--report-dir", default=str(REPORT_DIR_DEFAULT), help="Directory outside/inside repo for JSON/log reports.")
    parser.add_argument("--last", type=int, default=4, help="How many previous reports to summarize.")
    parser.add_argument("--no-clean", action="store_true", help="Skip local artifact cleanup before pytest.")
    parser.add_argument("--clean-only", action="store_true", help="Only clean local artifacts, do not run pytest.")
    parser.add_argument("--dry-run", action="store_true", help="Show cleanup plan without deleting local artifacts.")
    parser.add_argument("--deep-clean", action="store_true", help="Also remove heavyweight untracked build outputs such as Rust target dirs.")
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER, help="Arguments passed after -- to pytest counter.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = repo_root()
    report_dir = Path(args.report_dir).expanduser().resolve()
    pytest_args = list(args.pytest_args)
    if pytest_args and pytest_args[0] == "--":
        pytest_args = pytest_args[1:]
    if not pytest_args:
        pytest_args = ["--import-mode=importlib", "--tb=short", "tests"]

    if not args.no_clean:
        summary = clean_local_artifacts(root, dry_run=bool(args.dry_run), deep_clean=bool(args.deep_clean))
        print("[maintenance] cleanup=" + json.dumps(summary, ensure_ascii=False, sort_keys=True))

    if args.clean_only or args.dry_run:
        print_last_reports(report_dir, limit=max(1, int(args.last)))
        return 0

    rc, json_path, log_path = run_pytest_count(root, report_dir, pytest_args)
    if not args.no_clean:
        summary = clean_local_artifacts(root, dry_run=False, deep_clean=bool(args.deep_clean))
        print("[maintenance] post_cleanup=" + json.dumps(summary, ensure_ascii=False, sort_keys=True))
    print_report_summary(json_path)
    print_last_reports(report_dir, limit=max(1, int(args.last)))
    print("\n=== OUTPUT FILES ===")
    print(f"json: {json_path}")
    print(f"log:  {log_path}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
