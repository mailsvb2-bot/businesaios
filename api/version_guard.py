from __future__ import annotations


def assert_v1_path(path: str) -> None:
    if not path.startswith("/api/v1/"):
        raise ValueError("API path must be versioned: /api/v1/...")
