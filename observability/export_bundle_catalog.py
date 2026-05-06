from __future__ import annotations

CANON_COMPAT_SHIM = True

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from governance.persistence_codec import atomic_write_json, read_json_or_default
from observability.storage_coordination import advisory_file_lock
from observability.observability_bundle_policy import payload_sha256

CANON_EXPORT_BUNDLE_CATALOG = True


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class ExportBundleEntry:
    bundle_kind: str
    bundle_name: str
    path: str
    generated_at: str
    payload_sha256: str


class ExportBundleCatalog:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    @property
    def path(self) -> Path:
        return self._path

    def register(self, *, bundle_kind: str, bundle_name: str, path: str | Path, payload: Mapping[str, Any]) -> ExportBundleEntry:
        entry = ExportBundleEntry(
            bundle_kind=str(bundle_kind),
            bundle_name=str(bundle_name),
            path=str(Path(path)),
            generated_at=utc_now_iso(),
            payload_sha256=payload_sha256(payload),
        )
        with advisory_file_lock(self._path, exclusive=True):
            raw = read_json_or_default(self._path, default={"entries": []})
            entries = list(raw.get("entries", [])) if isinstance(raw, dict) else []
            entries = [item for item in entries if not (
                str(item.get("bundle_kind")) == entry.bundle_kind and str(item.get("bundle_name")) == entry.bundle_name
            )]
            entries.append(entry.__dict__)
            atomic_write_json(self._path, {"entries": entries})
        return entry

    def list_entries(self, *, bundle_kind: str | None = None) -> tuple[ExportBundleEntry, ...]:
        with advisory_file_lock(self._path, exclusive=False):
            raw = read_json_or_default(self._path, default={"entries": []})
        entries = list(raw.get("entries", [])) if isinstance(raw, dict) else []
        result: list[ExportBundleEntry] = []
        for item in entries:
            entry = ExportBundleEntry(
                bundle_kind=str(item.get("bundle_kind")),
                bundle_name=str(item.get("bundle_name")),
                path=str(item.get("path")),
                generated_at=str(item.get("generated_at")),
                payload_sha256=str(item.get("payload_sha256")),
            )
            if bundle_kind is None or entry.bundle_kind == str(bundle_kind):
                result.append(entry)
        result.sort(key=lambda item: (item.bundle_kind, item.generated_at, item.bundle_name))
        return tuple(result)

    def bundle_kinds(self) -> tuple[str, ...]:
        return tuple(sorted({entry.bundle_kind for entry in self.list_entries()}))

    def get(self, *, bundle_kind: str, bundle_name: str) -> ExportBundleEntry | None:
        for entry in self.list_entries(bundle_kind=bundle_kind):
            if entry.bundle_name == str(bundle_name):
                return entry
        return None

    def latest(self, *, bundle_kind: str) -> ExportBundleEntry | None:
        entries = self.list_entries(bundle_kind=bundle_kind)
        if not entries:
            return None
        return max(entries, key=lambda item: (item.generated_at, item.bundle_name))

    def remove(self, *, bundle_kind: str, bundle_name: str) -> ExportBundleEntry | None:
        removed: ExportBundleEntry | None = None
        with advisory_file_lock(self._path, exclusive=True):
            raw = read_json_or_default(self._path, default={"entries": []})
            entries = list(raw.get("entries", [])) if isinstance(raw, dict) else []
            kept: list[dict[str, str]] = []
            for item in entries:
                entry = ExportBundleEntry(
                    bundle_kind=str(item.get("bundle_kind")),
                    bundle_name=str(item.get("bundle_name")),
                    path=str(item.get("path")),
                    generated_at=str(item.get("generated_at")),
                    payload_sha256=str(item.get("payload_sha256")),
                )
                if removed is None and entry.bundle_kind == str(bundle_kind) and entry.bundle_name == str(bundle_name):
                    removed = entry
                    continue
                kept.append(dict(item))
            atomic_write_json(self._path, {"entries": kept})
        return removed

    def prune(self, *, bundle_kind: str | None = None, keep_latest: int = 20) -> tuple[ExportBundleEntry, ...]:
        removed: list[ExportBundleEntry] = []
        keep = max(1, int(keep_latest))
        with advisory_file_lock(self._path, exclusive=True):
            raw = read_json_or_default(self._path, default={"entries": []})
            entries = list(raw.get("entries", [])) if isinstance(raw, dict) else []
            grouped: dict[str, list[dict[str, str]]] = {}
            passthrough: list[dict[str, str]] = []
            for item in entries:
                kind = str(item.get("bundle_kind"))
                if bundle_kind is not None and kind != str(bundle_kind):
                    passthrough.append(dict(item))
                    continue
                grouped.setdefault(kind, []).append(dict(item))
            retained: list[dict[str, str]] = passthrough[:]
            for kind, items in grouped.items():
                items.sort(key=lambda item: (str(item.get("generated_at")), str(item.get("bundle_name"))))
                kept = items[-keep:]
                retained.extend(kept)
                for item in items[:-keep]:
                    removed.append(ExportBundleEntry(
                        bundle_kind=str(item.get("bundle_kind")),
                        bundle_name=str(item.get("bundle_name")),
                        path=str(item.get("path")),
                        generated_at=str(item.get("generated_at")),
                        payload_sha256=str(item.get("payload_sha256")),
                    ))
            atomic_write_json(self._path, {"entries": retained})
        return tuple(removed)

    def prune_missing(self, *, bundle_kind: str | None = None) -> tuple[ExportBundleEntry, ...]:
        removed: list[ExportBundleEntry] = []
        kept: list[dict[str, str]] = []
        with advisory_file_lock(self._path, exclusive=True):
            raw = read_json_or_default(self._path, default={"entries": []})
            entries = list(raw.get("entries", [])) if isinstance(raw, dict) else []
            for item in entries:
                entry = ExportBundleEntry(
                    bundle_kind=str(item.get("bundle_kind")),
                    bundle_name=str(item.get("bundle_name")),
                    path=str(item.get("path")),
                    generated_at=str(item.get("generated_at")),
                    payload_sha256=str(item.get("payload_sha256")),
                )
                if bundle_kind is not None and entry.bundle_kind != str(bundle_kind):
                    kept.append(dict(item))
                    continue
                if Path(entry.path).exists():
                    kept.append(dict(item))
                else:
                    removed.append(entry)
            atomic_write_json(self._path, {"entries": kept})
        return tuple(removed)


__all__ = ["CANON_EXPORT_BUNDLE_CATALOG", "ExportBundleCatalog", "ExportBundleEntry"]
