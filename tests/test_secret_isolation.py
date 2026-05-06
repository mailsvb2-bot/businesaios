import pathlib


FORBIDDEN_IMPORT = "infra.secrets"


def test_no_secret_import_in_core():
    core_path = pathlib.Path("core")

    for py in core_path.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        assert FORBIDDEN_IMPORT not in text, f"Secret leak in {py}"
