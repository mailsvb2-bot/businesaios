from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
import py_compile

import pytest

ROOT = Path(__file__).resolve().parents[2]
DOMAIN_KEYWORDS = {
    "billing": ("billing", "invoice", "payment", "refund", "quota", "economics", "spend", "client_outcome"),
    "app_web": ("web", "admin", "page", "component", "presentation"),
    "connectors_crm": ("connector", "connectors", "crm", "hubspot", "pipedrive"),
    "demand_routing_supply": ("demand", "intent", "match", "routing", "supply", "lead"),
    "product_quality_growth": ("product", "quality", "growth", "guardrail", "customer"),
    "ml_learning": ("ml", "learning", "model", "scoring", "inference"),
    "shared_registry": ("shared", "schema", "registry", "contract"),
}
DOMAIN_ROOTS = {
    "billing": ("billing/", "click_economics/", "economics/", "spend/"),
    "app_web": ("app/web/", "presentation/"),
    "connectors_crm": ("connectors/", "crm/"),
    "demand_routing_supply": ("demand_", "intent/", "matching/", "routing/", "routing_execution/", "supply_"),
    "product_quality_growth": ("product/", "quality/", "growth/", "guardrails/"),
    "ml_learning": ("ml/", "learning/"),
    "shared_registry": ("shared/", "schemas/", "registry/"),
}


def git_lines(*args: str) -> list[str]:
    out = subprocess.check_output(["git", *args], cwd=ROOT, text=True)
    return [line.strip() for line in out.splitlines() if line.strip()]


def changed_files(base: str) -> list[str]:
    merge_base = git_lines("merge-base", base, "HEAD")[0]
    return git_lines("diff", "--name-only", f"{merge_base}...HEAD")


def touched_domains(changed: list[str]) -> list[str]:
    domains: list[str] = []
    for domain, roots in DOMAIN_ROOTS.items():
        if any(path.startswith(roots) for path in changed):
            domains.append(domain)
    return domains


def _is_runnable_test_file(path: str) -> bool:
    name = Path(path).name
    if name == "conftest.py" or name.startswith("_"):
        return False
    return name.startswith("test_") or name.endswith("_test.py")


def matching_tests(domains: list[str]) -> list[str]:
    tests = [
        path
        for path in git_lines("ls-files", "tests/**/*.py")
        if _is_runnable_test_file(path)
    ]
    selected: set[str] = set()
    for domain in domains:
        for test in tests:
            lowered = test.lower()
            if any(keyword in lowered for keyword in DOMAIN_KEYWORDS[domain]):
                selected.add(test)
    return sorted(selected)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="origin/main")
    args = parser.parse_args()

    changed = changed_files(args.base)
    changed_py = [path for path in changed if path.endswith(".py") and (ROOT / path).is_file()]
    print(f"[targeted-ci] changed={len(changed)} changed_py={len(changed_py)}")

    for path in changed_py:
        py_compile.compile(str(ROOT / path), doraise=True)

    domains = touched_domains(changed)
    tests = matching_tests(domains)
    print(f"[targeted-ci] domains={domains}")
    print(f"[targeted-ci] tests={len(tests)}")
    for test in tests[:200]:
        print(f"[targeted-ci] test={test}")

    if not tests:
        print("[targeted-ci] no matching tests; compile check only")
        return 0
    return int(pytest.main(["-q", "-p", "pytest_asyncio.plugin", *tests]))


if __name__ == "__main__":
    sys.exit(main())
