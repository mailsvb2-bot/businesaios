import os


JUNK_PATTERNS = [
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".idea",
    ".vscode",
]


JUNK_EXTENSIONS = [
    ".pyc",
    ".pyo",
    ".bak",
    ".orig",
    "~",
]


def is_junk(path):
    for p in JUNK_PATTERNS:
        if p in path:
            return True

    for ext in JUNK_EXTENSIONS:
        if path.endswith(ext):
            return True

    return False


def scan_repo(root="."):
    junk_files = []

    for r, _, files in os.walk(root):
        for f in files:
            full = os.path.join(r, f)
            if is_junk(full):
                junk_files.append(full)

    return junk_files
