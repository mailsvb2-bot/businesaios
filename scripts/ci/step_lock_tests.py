from __future__ import annotations

from pathlib import Path

from scripts.ci.paths import repo_root
from scripts.ci.subprocess_io import run_python


def _repo_hygiene_files(root: Path):
    skip_dirs = {
        ".git", ".artifacts", "artifacts", ".venv", "venv", "__pycache__",
        ".pytest_cache", ".mypy_cache", ".ruff_cache", "node_modules", "dist",
    }
    for path in root.rglob("*"):
        if any(part in skip_dirs for part in path.parts):
            continue
        if path.is_file():
            yield path


def _bounded_text_files(root: Path):
    text_names = {"Dockerfile", "Makefile", ".gitignore"}
    text_suffixes = {
        ".py", ".md", ".yml", ".yaml", ".toml", ".ini", ".json", ".txt", ".sh", ".env", ".cfg",
    }
    for path in _repo_hygiene_files(root):
        try:
            if path.stat().st_size > 2_000_000:
                continue
        except OSError:
            continue
        if path.name in text_names or path.suffix.lower() in text_suffixes:
            yield path


def _direct_repo_hygiene_lock() -> tuple[bool, str]:
    root = repo_root()
    conflict_hits: list[str] = []
    patch_hits: list[str] = []
    archive_hits: list[str] = []
    for path in _repo_hygiene_files(root):
        rel = path.relative_to(root).as_posix()
        suffix = path.suffix.lower()
        if suffix in {".rej", ".orig", ".bak"}:
            patch_hits.append(rel)
        if suffix in {".zip", ".tar", ".tgz", ".gz", ".7z", ".rar", ".sqlite", ".sqlite3", ".db"}:
            archive_hits.append(rel)

    left_marker = ("<" * 7).encode()
    right_marker = (">" * 7).encode()
    for path in _bounded_text_files(root):
        rel = path.relative_to(root).as_posix()
        if rel.startswith("tests/"):
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if left_marker in data or right_marker in data:
            conflict_hits.append(rel)

    if conflict_hits:
        return False, "merge conflict markers found: " + ", ".join(sorted(conflict_hits)[:20])
    if patch_hits:
        return False, "patch/backup artifacts found: " + ", ".join(sorted(patch_hits)[:20])
    if archive_hits:
        return False, "forbidden archive/db artifacts found: " + ", ".join(sorted(archive_hits)[:20])
    return True, "repo hygiene locks passed"


def _direct_cicd_contract_lock() -> tuple[bool, str]:
    from tests.lock.test_lock_cicd_contract_files_present import REQUIRED

    root = repo_root()
    missing = [rel for rel in REQUIRED if not (root / rel).exists()]
    if missing:
        return False, f"missing ci/cd contract files: {missing}"
    return True, "ci/cd contract lock passed"


def _direct_second_brain_surface_lock() -> tuple[bool, str]:
    from tests.arch.test_agi_no_second_brain_surfaces import FORBIDDEN_SURFACES

    offenders = [rel for rel in FORBIDDEN_SURFACES if (repo_root() / rel).exists()]
    if offenders:
        return False, "forbidden second-brain surfaces exist: " + ", ".join(offenders)
    return True, "second-brain surface lock passed"


def _direct_multimessenger_runtime_lock() -> tuple[bool, str]:
    from scripts.ci.multimessenger_contract import (
        verify_multimessenger_runtime_contract,
    )

    return verify_multimessenger_runtime_contract()


def _direct_runtime_decision_execution_service_name_lock() -> tuple[bool, str]:
    root = repo_root()
    service_names = (root / "runtime" / "service_names.py").read_text(encoding="utf-8")
    registry_state = (root / "runtime" / "registry_state.py").read_text(encoding="utf-8")
    registration = (root / "boot" / "registrations" / "register_decision_core.py").read_text(encoding="utf-8")
    service_specs = (root / "bootstrap" / "runtime_service_specs.py").read_text(encoding="utf-8")
    runtime_policies = (root / "runtime" / "runtime_policies.py").read_text(encoding="utf-8")

    required_snippets = {
        "runtime/service_names.py": (
            "RUNTIME_DECISION_EXECUTION_SERVICE",
            "canonical_runtime_service_name",
            "CANON_RUNTIME_DECISION_CORE_SERVICE_NAME_COMPAT_ALIAS",
        ),
        "runtime/registry_state.py": ("canonical_runtime_service_name(name)",),
        "boot/registrations/register_decision_core.py": (
            "name=RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE",
            "service_type=RuntimeServiceType.EXECUTOR",
            "CANON_REGISTER_DECISION_CORE_SERVICE_NAME_COMPAT_ALIAS_ONLY",
        ),
        "bootstrap/runtime_service_specs.py": (
            "RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE",
            "CANON_RUNTIME_DECISION_EXECUTION_SERVICE_MANIFEST_NAME",
        ),
        "runtime/runtime_policies.py": ("RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE",),
    }
    text_by_file = {
        "runtime/service_names.py": service_names,
        "runtime/registry_state.py": registry_state,
        "boot/registrations/register_decision_core.py": registration,
        "bootstrap/runtime_service_specs.py": service_specs,
        "runtime/runtime_policies.py": runtime_policies,
    }
    missing: list[str] = []
    for rel, snippets in required_snippets.items():
        for snippet in snippets:
            if snippet not in text_by_file[rel]:
                missing.append(f"{rel}:{snippet}")
    if missing:
        return False, "runtime decision execution service naming lock missing snippets: " + ", ".join(missing)

    forbidden_registration = "name=RuntimeServiceName." + "DECISION_CORE"
    forbidden_spec = "service_name=RuntimeServiceName." + "DECISION_CORE"
    forbidden_policy = "RuntimeServiceName." + "DECISION_CORE"
    offenders: list[str] = []
    if forbidden_registration in registration:
        offenders.append("boot/registrations/register_decision_core.py registers execution under decision core name")
    if forbidden_spec in service_specs:
        offenders.append("bootstrap/runtime_service_specs.py manifests execution under decision core name")
    if forbidden_policy in runtime_policies:
        offenders.append("runtime/runtime_policies.py requires decision core alias")
    if offenders:
        return False, "runtime decision execution service naming lock failed: " + "; ".join(offenders)

    code = r'''
from runtime.registry import RuntimeRegistry
from runtime.service_names import RuntimeServiceName, canonical_runtime_service_name
from runtime.service_types import RuntimeServiceType

service = object()
registry = RuntimeRegistry()
registry.begin_registration()
registry.register(
    name=RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE,
    service=service,
    service_type=RuntimeServiceType.EXECUTOR,
)
if canonical_runtime_service_name(RuntimeServiceName.DECISION_CORE) != RuntimeServiceName.RUNTIME_DECISION_EXECUTION_SERVICE:
    print("decision_core alias does not resolve to execution service")
    raise SystemExit(1)
if registry.get(RuntimeServiceName.DECISION_CORE) is not service:
    print("legacy decision_core lookup no longer resolves to execution service")
    raise SystemExit(1)
if RuntimeServiceName.DECISION_CORE in registry.list_service_names():
    print("registry stores legacy decision_core alias as canonical service name")
    raise SystemExit(1)
print("runtime decision execution service naming lock passed")
'''
    outcome = run_python(["-c", code], timeout=30)
    if outcome.returncode != 0:
        return False, outcome.stdout.strip() or outcome.stderr.strip() or "runtime decision execution service naming lock failed"
    return True, "runtime decision execution service naming lock passed"


def _direct_container_release_lock_install_path() -> tuple[bool, str]:
    root = repo_root()
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    release_lock_path = root / "requirements.release.lock.txt"
    if not release_lock_path.exists():
        return False, "requirements.release.lock.txt is required for container production install"
    release_lock = release_lock_path.read_text(encoding="utf-8")
    required = (
        "COPY requirements.release.lock.txt",
        "pip install --require-hashes -r requirements.release.lock.txt",
        "BAIOS_REQUIRE_TRANSITIVE_DEPENDENCY_LOCK=1",
    )
    missing = [snippet for snippet in required if snippet not in dockerfile]
    if missing:
        return False, "container release dependency install path missing: " + ", ".join(missing)
    forbidden = (
        "COPY requirements.lock.txt",
        "pip install -r requirements.lock.txt",
        "pip install -r requirements.txt",
    )
    hits = [snippet for snippet in forbidden if snippet in dockerfile]
    if hits:
        return False, "container production install uses non-release lock path: " + ", ".join(hits)
    if "BAIOS_TRANSITIVE_LOCK: true" not in release_lock or "--hash=sha256:" not in release_lock:
        return False, "requirements.release.lock.txt does not prove transitive hash locking"
    if "Transitive dependency locking can be added later" in release_lock:
        return False, "requirements.release.lock.txt is marked as top-level-only"
    return True, "container release dependency install path lock passed"


def _direct_ai_ceo_lock() -> tuple[bool, str]:
    root = repo_root()
    needle = "ai" + "_ceo" + "_plan" + "@v1"
    allowed_prefixes = tuple(
        str(root / rel) for rel in (
            "core/ai_ceo",
            "core/policies/telegram/handlers/ai_ceo.py",
            "runtime/handlers/ai_ceo_plan.py",
            "runtime/boot/actions_catalog.py",
            "runtime/boot/actions_registry.py",
            "runtime/boot/registration_manifest.py",
        )
    )
    hits: list[str] = []
    offenders: list[str] = []
    for path in root.rglob("*.py"):
        if "tests" in path.parts or "artifacts" in path.parts or "__pycache__" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if needle in text:
            full = str(path)
            hits.append(path.relative_to(root).as_posix())
            if not any(full.startswith(prefix) for prefix in allowed_prefixes):
                offenders.append(path.relative_to(root).as_posix())
    if not hits:
        return False, "expected canonical AI CEO action to be referenced"
    if offenders:
        return False, "unexpected AI CEO second-path references: " + ", ".join(sorted(offenders)[:20])
    return True, "AI CEO single-path lock passed"


def _direct_runtime_actions_registry_lock() -> tuple[bool, str]:
    runtime_import = "from " + "runtime.boot.actions_registry" + " import SPECS, INLINE_ALLOWLIST, all_actions\n"
    manifest_import = "from " + "runtime.boot.registration_manifest" + " import registered_action_names\n"
    code = (
        "import os\n"
        "import re\n"
        "from pathlib import Path\n"
        + runtime_import
        + manifest_import
        + r'''
root = Path.cwd()
expected = all_actions()
registered = set(registered_action_names())
if registered != expected:
    print(f"runtime registry drift: missing={sorted(expected-registered)} extra={sorted(registered-expected)}")
    os._exit(1)

offenders = []
for path in (root / "runtime").rglob("*.py"):
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        continue
    for action in re.findall(r'handlers\.register\(\s*"([^"]+)"', text):
        if action not in expected:
            offenders.append(f"{path.relative_to(root).as_posix()}:{action}")
if offenders:
    print("unregistered runtime-actions found: " + ", ".join(sorted(offenders)[:20]))
    os._exit(1)

read_only = {"noop@v1", "poll_telegram_updates@v1", "telegram_self_check@v1"}
for name, spec in SPECS.items():
    if spec.name != name:
        print(f"runtime action spec name mismatch for {name}")
        os._exit(1)
    if spec.limits is None:
        print(f"runtime action lacks limits: {name}")
        os._exit(1)
    if name == "noop@v1":
        if spec.limits.kind != "none":
            print("noop@v1 must have none limits")
            os._exit(1)
    elif spec.limits.kind == "none" or spec.limits.per_tenant_per_min <= 0 or spec.limits.per_user_per_min <= 0:
        print(f"runtime action invalid limits: {name}")
        os._exit(1)
    if not spec.handler_ref or not isinstance(spec.handler_ref, str):
        print(f"runtime action missing handler_ref: {name}")
        os._exit(1)
    if name not in INLINE_ALLOWLIST and not spec.handler_ref.startswith(("runtime.handlers.", "runtime.handlers_")):
        print(f"runtime action invalid handler_ref: {name}:{spec.handler_ref}")
        os._exit(1)
    expected_idempotency = name not in read_only
    if spec.requires_idempotency_key is not expected_idempotency:
        print(f"runtime action idempotency mismatch: {name}")
        os._exit(1)
print("runtime actions registry lock passed")
os._exit(0)
'''
    )
    outcome = run_python(["-c", code], timeout=90)
    if outcome.returncode != 0:
        return False, outcome.stdout.strip() or outcome.stderr.strip() or "runtime actions registry lock failed"
    return True, "runtime actions registry lock passed"


def run() -> tuple[bool, str]:
    checks = (
        _direct_repo_hygiene_lock,
        _direct_cicd_contract_lock,
        _direct_second_brain_surface_lock,
        _direct_multimessenger_runtime_lock,
        _direct_runtime_decision_execution_service_name_lock,
        _direct_container_release_lock_install_path,
        _direct_ai_ceo_lock,
        _direct_runtime_actions_registry_lock,
    )
    messages: list[str] = []
    for check in checks:
        ok, message = check()
        if not ok:
            return False, message
        messages.append(message)
    return True, "; ".join(messages)


__all__ = ["run"]
