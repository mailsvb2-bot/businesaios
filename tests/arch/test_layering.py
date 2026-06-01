import ast
import pathlib

RUNTIME_PLATFORM_CORE_IMPORT_ALLOWLIST = {
    pathlib.Path("runtime/platform/support/policy/policy_factory.py"),
    pathlib.Path("runtime/platform/support/policy/policy_registry.py"),
}


def _imports_in_file(path: pathlib.Path):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return []
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                out.append(node.module)
    return out


def test_no_platform_or_runtime_import_in_core_policies():
    root = pathlib.Path("core") / "policies"
    if not root.exists():
        return
    for f in root.rglob("*.py"):
        for mod in _imports_in_file(f):
            assert not mod.startswith("runtime.platform"), f"runtime.platform import leak: {f} -> {mod}"
            assert not mod.startswith("runtime"), f"runtime import leak: {f} -> {mod}"


def test_no_core_import_in_runtime_platform():
    root = pathlib.Path("runtime/platform")
    if not root.exists():
        return
    for f in root.rglob("*.py"):
        if f in RUNTIME_PLATFORM_CORE_IMPORT_ALLOWLIST:
            continue
        file_text = f.read_text(encoding="utf-8", errors="ignore")
        if "CANON_COMPAT_SHIM = True" in file_text:
            continue
        for mod in _imports_in_file(f):
            assert not mod.startswith("core"), f"core import leak: {f} -> {mod}"
