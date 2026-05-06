import pathlib
import re


def _scan_py_files(root: pathlib.Path) -> list[pathlib.Path]:
    return [p for p in root.rglob("*.py") if p.is_file()]


def test_no_platform_import_in_policies():
    root = pathlib.Path("core/policies")
    for file in _scan_py_files(root):
        text = file.read_text(encoding="utf-8")
        assert "runtime.platform" not in text, f"policy imports runtime.platform: {file}"


def test_no_runtime_import_in_policies():
    root = pathlib.Path("core/policies")
    for file in _scan_py_files(root):
        text = file.read_text(encoding="utf-8")
        # allow typing-only mentions in docs? keep strict.
        assert re.search(r"\bimport\s+runtime\b", text) is None, f"policy imports runtime: {file}"
        assert re.search(r"\bfrom\s+runtime\b", text) is None, f"policy imports runtime: {file}"


def test_no_executor_import_in_read_models():
    root = pathlib.Path("core")
    for file in _scan_py_files(root):
        if "read" not in file.name and "read_model" not in file.name and "readmodel" not in file.name:
            continue
        text = file.read_text(encoding="utf-8")
        assert "runtime.executor" not in text, f"read-model imports executor: {file}"
        assert "RuntimeExecutor" not in text, f"read-model imports RuntimeExecutor: {file}"
