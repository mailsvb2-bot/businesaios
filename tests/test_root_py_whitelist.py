import pathlib


def test_root_py_files_are_whitelisted_only():
    """Production root must not contain arbitrary python entrypoints.

    Allowed root .py files:
      - main.py (single entrypoint)
      - sitecustomize.py / usercustomize.py (python runtime hooks)
    """
    root = pathlib.Path(__file__).resolve().parents[1]
    allowed = {"main.py", "sitecustomize.py", "usercustomize.py"}

    root_py = {p.name for p in root.glob("*.py")}

    assert root_py <= allowed, (
        "Forbidden .py files detected in repo root: "
        f"{sorted(root_py - allowed)}"
    )
