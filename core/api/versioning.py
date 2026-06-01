from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class ApiVersion:
    major: int
    minor: int = 0

    @staticmethod
    def parse(v: str | None, *, default: ApiVersion) -> ApiVersion:
        raw = (v or "").strip().lstrip("v").strip()
        if not raw:
            return default
        parts = raw.split(".")
        try:
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
        except Exception:
            return default
        if major < 0 or minor < 0:
            return default
        return ApiVersion(major=major, minor=minor)

    def str_tag(self) -> str:
        return f"v{self.major}.{self.minor}"

    def matches_major(self, other: ApiVersion) -> bool:
        return self.major == other.major


DEFAULT_API_VERSION = ApiVersion(major=1, minor=0)


class ApiVersionUnsupported(RuntimeError):
    pass


def parse_api_version(v: str | None, *, default: ApiVersion = DEFAULT_API_VERSION) -> ApiVersion:
    return ApiVersion.parse(v, default=default)


def require_min_version(got: ApiVersion, *, min_version: ApiVersion) -> None:
    if got < min_version:
        raise ApiVersionUnsupported(
            f"API_VERSION_TOO_OLD got={got.str_tag()} min={min_version.str_tag()}"
        )


def require_max_version(got: ApiVersion, *, max_version: ApiVersion) -> None:
    if got > max_version:
        raise ApiVersionUnsupported(
            f"API_VERSION_TOO_NEW got={got.str_tag()} max={max_version.str_tag()}"
        )
