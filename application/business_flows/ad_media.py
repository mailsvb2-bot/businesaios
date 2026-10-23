"""Ad publication media ledger (port of clientplatform ad_publication_assets).

Replayed from facts, one asset per publication job. Upload goes through an injected
``uploader`` (default: dry-run, deterministic ``dryrun:`` reference, no provider call).
Invariants kept from the donor: at-most-once provider write per (job, sha256); an
exception after claim marks the upload *ambiguous* and blocks automatic retry; only
provider-side references are stored, never media bytes.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

IMAGE_INPUT_LIMIT, VIDEO_LIMIT = 20_000_000, 100_000_000
VIDEO_EXTENSIONS = frozenset({"mp4", "webm", "mov", "qt", "flv", "avi"})
VIDEO_TYPES = frozenset({"video/mp4", "video/webm", "video/quicktime", "video/x-flv", "video/x-msvideo", "application/octet-stream"})
IMAGE_MAGIC = {b"\xff\xd8\xff": "image/jpeg", b"\x89PNG\r\n\x1a\n": "image/png", b"GIF8": "image/gif"}


class AssetError(ValueError):
    pass


@dataclass(frozen=True)
class Asset:
    job_id: str
    kind: str
    sha256: str
    size_bytes: int
    content_type: str
    name: str
    state: str  # uploading | ready | ambiguous | failed
    connection_id: str = ""
    duration_seconds: int | None = None
    image_hash: str = ""
    video_id: str = ""
    creative_id: str = ""
    error: str = ""


def replay(payloads: list[dict[str, Any]]) -> dict[str, Asset]:
    out: dict[str, Asset] = {}
    for p in payloads:
        step, job = p.get("step"), str(p.get("job_id") or "")
        cur = out.get(job)
        if step == "ad_media_reserved" and (cur is None or cur.state == "failed"):
            out[job] = Asset(job, p["kind"], p["sha256"], int(p["size_bytes"]), p["content_type"], p["name"],
                             "uploading", p.get("connection_id", ""), p.get("duration_seconds"))
        elif cur is None:
            continue
        elif step == "ad_media_ready" and cur.state == "uploading":
            out[job] = replace(cur, state="ready", image_hash=p.get("image_hash", ""), video_id=p.get("video_id", ""))
        elif step == "ad_media_ambiguous" and cur.state == "uploading":
            out[job] = replace(cur, state="ambiguous", error=p.get("error", ""))
        elif step == "ad_media_provider_ids":
            out[job] = replace(cur, **{k: p[k] for k in ("image_hash", "video_id", "creative_id") if p.get(k)})
        elif step == "ad_media_provider_error":
            out[job] = replace(cur, error=str(p.get("error") or "")[:64])
        elif step == "ad_media_removed":
            out.pop(job, None)
    return out


def sniff_image(payload: bytes) -> str:
    if not payload or len(payload) > IMAGE_INPUT_LIMIT:
        raise AssetError("image is too large")
    if payload[:4] == b"RIFF" and payload[8:12] == b"WEBP":
        return "image/webp"
    for magic, ctype in IMAGE_MAGIC.items():
        if payload.startswith(magic):
            return ctype
    raise AssetError("image format is unsupported or damaged")


def video_suffix(payload: bytes, content_type: str, name: str, duration_seconds: int) -> tuple[str, str]:
    if not payload or len(payload) > VIDEO_LIMIT:
        raise AssetError("video must be no larger than 100 MB")
    if not 5 <= int(duration_seconds) <= 60:
        raise AssetError("video duration must be between 5 and 60 seconds")
    ctype = str(content_type or "application/octet-stream").strip().lower()
    if ctype not in VIDEO_TYPES:
        raise AssetError("video format is unsupported")
    suffix = str(name or "video.mp4").rsplit(".", 1)[-1].lower()
    if suffix not in VIDEO_EXTENSIONS:
        suffix = {"video/mp4": "mp4", "video/webm": "webm", "video/quicktime": "mov"}.get(ctype, "")
        if not suffix:
            raise AssetError("video file extension is unsupported")
    return ctype, suffix


def reservation_result(cur: Asset | None, sha: str) -> Asset | None:
    """Donor _reservation_result: reuse a ready upload of the same bytes; block in-flight/ambiguous."""
    if cur is None or cur.state == "failed":
        return None
    if cur.state == "ready" and cur.sha256 == sha:
        return cur
    if cur.state == "uploading":
        raise AssetError("advertising media upload is already in progress")
    if cur.state == "ambiguous":
        raise AssetError("advertising media upload result is ambiguous; automatic retry is blocked")
    raise AssetError("job already has a different asset; remove it first")


Uploader = Callable[[str, bytes, str], str]  # (kind, payload, name) -> provider reference


def dry_run_uploader(kind: str, payload: bytes, name: str) -> str:
    return "dryrun:" + hashlib.sha256(payload).hexdigest()[:24]


def _attach(assets, job_id, kind, payload, ctype, name, uploader, connection_id, duration) -> tuple[Asset | None, list[dict[str, Any]]]:
    sha = hashlib.sha256(payload).hexdigest()
    existing = reservation_result(assets.get(job_id), sha)
    if existing is not None:
        return existing, []
    reserved = {"step": "ad_media_reserved", "job_id": job_id, "kind": kind, "sha256": sha, "size_bytes": len(payload),
                "content_type": ctype, "name": name, "connection_id": connection_id, "duration_seconds": duration}
    try:
        ref = uploader(kind, payload, name)
    except Exception as exc:  # noqa: BLE001 - donor: any provider failure after claim is ambiguous
        return None, [reserved, {"step": "ad_media_ambiguous", "job_id": job_id,
                                 "error": f"ad_{kind}_upload_ambiguous:{type(exc).__name__}"}]
    key = "image_hash" if kind == "image" else "video_id"
    return None, [reserved, {"step": "ad_media_ready", "job_id": job_id, key: str(ref)}]


def attach_image(assets: dict[str, Asset], job_id: str, payload: bytes, *, name: str = "image.jpg",
                 uploader: Uploader = dry_run_uploader, connection_id: str = "") -> tuple[Asset | None, list[dict[str, Any]]]:
    return _attach(assets, job_id, "image", payload, sniff_image(payload), name or "image.jpg", uploader, connection_id, None)


def attach_image_file(assets: dict[str, Asset], job_id: str, path: Path, **kw: Any) -> tuple[Asset | None, list[dict[str, Any]]]:
    candidate = Path(path).expanduser()
    if candidate.is_symlink() or not candidate.resolve(strict=True).is_file():
        raise AssetError("generated image is unavailable")
    if candidate.stat().st_size > IMAGE_INPUT_LIMIT:
        raise AssetError("generated image is too large")
    return attach_image(assets, job_id, candidate.read_bytes(), name=candidate.name, **kw)


def attach_video(assets: dict[str, Asset], job_id: str, payload: bytes, *, content_type: str, name: str,
                 duration_seconds: int, uploader: Uploader = dry_run_uploader,
                 connection_id: str = "") -> tuple[Asset | None, list[dict[str, Any]]]:
    ctype, suffix = video_suffix(payload, content_type, name, duration_seconds)
    return _attach(assets, job_id, "video", payload, ctype, name or f"video.{suffix}", uploader, connection_id, int(duration_seconds))


def reusable_images(assets: dict[str, Asset], *, connection_id: str, exclude_job: str, limit: int = 8) -> list[Asset]:
    seen, out = set(), []
    for a in assets.values():
        if a.kind == "image" and a.state == "ready" and a.connection_id == connection_id and a.job_id != exclude_job and a.image_hash not in seen:
            seen.add(a.image_hash)
            out.append(a)
    return out[: max(1, min(int(limit), 50))]


def reuse_image(assets: dict[str, Asset], source_job: str, target_job: str) -> list[dict[str, Any]]:
    src = assets.get(source_job)
    if src is None or src.kind != "image" or src.state != "ready":
        raise AssetError("advertising image provider reference could not be reused")
    if target_job in assets:
        raise AssetError("target job already has an asset")
    return [{"step": "ad_media_reserved", "job_id": target_job, "kind": "image", "sha256": src.sha256,
             "size_bytes": src.size_bytes, "content_type": src.content_type, "name": src.name,
             "connection_id": src.connection_id, "duration_seconds": None},
            {"step": "ad_media_ready", "job_id": target_job, "image_hash": src.image_hash}]


def remove(assets: dict[str, Asset], job_id: str) -> dict[str, Any] | None:
    return {"step": "ad_media_removed", "job_id": job_id} if job_id in assets else None


def provider_ids(job_id: str, **ids: str | None) -> dict[str, Any]:
    return {"step": "ad_media_provider_ids", "job_id": job_id, **{k: v for k, v in ids.items() if v}}
