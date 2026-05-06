from __future__ import annotations

import os

from scripts.ci.paths import hooks_dir, repo_root


def main() -> int:
    root = repo_root()
    git_hooks = root / ".git" / "hooks"
    if not git_hooks.exists():
        raise FileNotFoundError(".git/hooks not found; initialize git repository first")

    source = hooks_dir() / "pre-push"
    target = git_hooks / "pre-push"

    if not source.exists():
        raise FileNotFoundError(f"hook source missing: {source}")

    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    os.chmod(target, 0o755)
    print(f"[ci] installed pre-push hook to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
