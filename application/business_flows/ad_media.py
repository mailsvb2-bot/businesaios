"""Ad publication media ledger (port of clientplatform ad_publication_assets).

Replayed from facts, one asset per publication job. Upload goes through an injected
``uploader`` (default: dry-run, deterministic ``dryrun:`` reference, no provider call).
Invariants kept from the donor: at-most-once provider write per (job, sha256); an
exception after claim marks the upload *ambiguous* and blocks automatic retry; only
provider-side references are stored, never media bytes.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
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


IMAGE_OUTPUT_LIMIT = 10_000_000


def normalize_image(payload: bytes) -> bytes:
    """1080x1080 white-padded JPEG (q90), EXIF-oriented. Pillow is optional: not a repo dependency."""
    if not payload or len(payload) > IMAGE_INPUT_LIMIT:
        raise AssetError("image is too large")
    try:
        from io import BytesIO

        from PIL import Image, ImageOps, UnidentifiedImageError
    except ImportError as exc:  # pragma: no cover - depends on optional install
        raise AssetError("image normalization unavailable (Pillow not installed)") from exc
    try:
        with Image.open(BytesIO(payload)) as src:
            src.verify()
        with Image.open(BytesIO(payload)) as again:
            img = ImageOps.contain(ImageOps.exif_transpose(again).convert("RGB"), (1080, 1080),
                                   method=Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", (1080, 1080), "white")
            canvas.paste(img, ((1080 - img.width) // 2, (1080 - img.height) // 2))
            out = BytesIO()
            canvas.save(out, format="JPEG", quality=90, optimize=True)
            data = out.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise AssetError("image format is unsupported or damaged") from exc
    if not data or len(data) > IMAGE_OUTPUT_LIMIT:
        raise AssetError("image could not be normalized for advertising")
    return data


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


# --- goal studio publication (port of donor creative_studio_publication) ---
# A selected studio variant is bound to an ad publication job via facts; the executor's
# generate_visual_creative/poll_visual_creative jobs (with render pack) drive progress, and the
# rendered square is attached through attach_image_file (dry-run uploader by default).

GOAL_FORMATS = ("square", "feed", "story", "landscape")
GOAL_LABELS = ("🤝 Доверие и живой человек", "🧭 Понятный процесс", "✨ Спокойная ценность")
PLACEMENT_RENDER_FORMATS = {"yandex_direct": "square"}  # canonical Yandex bridge normalises to square


class PublicationError(RuntimeError):
    pass


@dataclass(frozen=True)
class VariantBinding:
    job_id: str
    creative_id: str
    business_id: str
    angle: str
    source_job_id: str = ""
    render_pack_id: str = ""
    status: str = "selected"  # selected | generating | rendering | failed | attached


def render_format_for_placement(placement: str) -> str:
    try:
        return PLACEMENT_RENDER_FORMATS[str(placement or "").strip().lower()]
    except KeyError as exc:
        raise ValueError("unsupported_creative_publication_placement") from exc


def goal_variant_labels(variants: tuple[Any, ...]) -> tuple[str, ...]:
    if len(variants) != len(GOAL_LABELS):
        raise ValueError("unexpected_goal_studio_variant_count")
    return GOAL_LABELS


def selected_goal_variant(variants: tuple[Any, ...], index: int) -> Any:
    i = int(index)
    if not 0 <= i < len(variants):
        raise ValueError("creative_variant_index_out_of_range")
    return variants[i]


def replay_bindings(facts: list[dict[str, Any]]) -> dict[str, VariantBinding]:
    out: dict[str, VariantBinding] = {}
    for f in facts:
        step, job = f.get("step"), str(f.get("job_id") or "")
        if step == "creative_variant_selected":
            out[job] = VariantBinding(job, str(f["creative_id"]), str(f["business_id"]), str(f.get("angle") or ""))
        elif step == "creative_variant_progress" and job in out and out[job].creative_id == f.get("creative_id"):
            out[job] = replace(out[job], source_job_id=str(f.get("source_job_id") or ""),
                               render_pack_id=str(f.get("render_pack_id") or ""), status=str(f["status"]))
    return out


def select_variant(job_id: str, brief: Any, *, business_id: str) -> dict[str, Any]:
    """Donor _select_binding: (re)select which studio variant this publication job uses."""
    if brief.business_id != business_id:
        raise ValueError("creative_variant_business_mismatch")
    return {"step": "creative_variant_selected", "job_id": job_id, "creative_id": brief.creative_id,
            "business_id": business_id, "angle": brief.angle, "campaign_id": brief.campaign_id}


def _progress_fact(job_id: str, brief: Any, source_job_id: str, render_pack_id: str, status: str) -> dict[str, Any]:
    return {"step": "creative_variant_progress", "job_id": job_id, "creative_id": brief.creative_id,
            "source_job_id": source_job_id, "render_pack_id": render_pack_id, "status": status}


def check_binding(bindings: dict[str, VariantBinding], job_id: str, brief: Any, source_job_id: str) -> VariantBinding:
    current = bindings.get(job_id)
    if current is None or current.creative_id != brief.creative_id:
        raise ValueError("creative_variant_binding_changed")
    if current.source_job_id and current.source_job_id != str(source_job_id or "").strip():
        raise ValueError("creative_source_job_binding_changed")
    return current


def progress(*, bindings: dict[str, VariantBinding], assets: dict[str, Asset], job_id: str, brief: Any,
             visual_job: dict[str, Any], placement: str = "yandex_direct",
             fetch_render: Callable[[dict[str, Any], str], Path] | None = None,
             uploader: Uploader | None = None, normalize: bool = True) -> tuple[str, list[dict[str, Any]]]:
    """Donor _progress_result/_attach_render over an executor visual job dict (with ``render_pack``)."""
    fmt = render_format_for_placement(placement)
    vid = str(visual_job.get("id") or "")
    check_binding(bindings, job_id, brief, vid)
    render = visual_job.get("render_pack") if isinstance(visual_job.get("render_pack"), dict) else None
    state = str(visual_job.get("status") or "")
    if state == "failed" or (render is not None and render.get("status") == "failed"):
        status = "failed"
    elif state in {"queued", "running"}:
        status = "generating"
    elif render is None or render.get("status") in {None, "", "running", "queued"}:
        status = "rendering"
    else:
        if render.get("status") != "succeeded":
            raise PublicationError("creative_render_not_ready")
        if str(render.get("scope_id") or brief.tenant_id) != brief.tenant_id or str(
                render.get("source_job_id") or vid) != vid:
            raise PublicationError("creative_render_binding_mismatch")
        if fmt not in brief.formats:
            raise PublicationError("creative_render_format_not_requested")
        if fetch_render is None:
            raise PublicationError("creative_asset_attachment_failed")
        try:
            path = fetch_render(render, fmt)
            if normalize:
                from application.business_flows.visual_creatives import normalize_image
                normalize_image(path)
            kw: dict[str, Any] = {} if uploader is None else {"uploader": uploader}
            _asset, facts = attach_image_file(assets, job_id, path, **kw)
        except (AssetError, OSError, ValueError) as exc:
            raise PublicationError("creative_asset_attachment_failed") from exc
        return "attached", [*facts, _progress_fact(job_id, brief, vid, str(render.get("id") or ""), "attached")]
    return status, [_progress_fact(job_id, brief, vid, "" if render is None else str(render.get("id") or ""), status)]


def observable_variants(bindings: dict[str, VariantBinding]) -> list[VariantBinding]:
    """Attached bindings that ad statistics can attribute to a studio angle."""
    return [b for b in bindings.values() if b.status == "attached"]


# --- editable advertising project (donor editable_advertising + EditableAdProjectRepository) ---
# Composition metadata only (never media bytes). Event-sourced from ``eap_*`` facts; the provider
# poll/render is an executor effect, the pure rules below decide what its result means.

_COLOR = re.compile(r"#[0-9A-Fa-f]{6}")
FONT_PRESETS = ("auto", "modern", "strict", "friendly", "premium", "editorial", "elegant", "bold_ad")
LAYOUTS = ("lower_card", "top_card")
EDITABLE_PUBLICATION_STATES = frozenset({"draft", "failed", "submitted"})
DEFAULT_BRAND = {"primary_color": "#172033", "accent_color": "#E9C46A", "text_color": "#FFFFFF"}
DEFAULT_FORMATS = ("square",)


class EditableAdError(RuntimeError):
    """Sanitized editable-ad orchestration failure."""


class EditableAdSourceExpired(EditableAdError):
    """The exact AI source completed earlier but its transient bytes are gone."""


@dataclass(frozen=True, slots=True)
class EditableAdProject:
    id: str
    member_id: str
    publication_job_id: str
    kind: str
    headline: str
    body: str
    cta: str
    layout: str
    font_preset: str
    brand_json: str
    source_job_id: str = ""
    status: str = "draft"  # draft | source_ready | source_expired | finished
    revision: int = 1
    created_at: str = ""
    updated_at: str = ""

    def brand(self) -> dict[str, str]:
        try:
            value = json.loads(self.brand_json)
        except json.JSONDecodeError as exc:
            raise ValueError("editable_ad_brand_invalid") from exc
        if not isinstance(value, dict) or set(value) != set(DEFAULT_BRAND):
            raise ValueError("editable_ad_brand_invalid")
        out = {k: str(value.get(k) or "").strip().upper() for k in DEFAULT_BRAND}
        if any(_COLOR.fullmatch(v) is None for v in out.values()):
            raise ValueError("editable_ad_brand_invalid")
        return out

    def composition(self) -> dict[str, object]:
        if self.kind not in {"image", "video"}:
            raise ValueError("editable_ad_kind_invalid")
        if self.layout not in LAYOUTS:
            raise ValueError("editable_ad_layout_invalid")
        if self.revision < 1:
            raise ValueError("editable_ad_revision_invalid")
        return {
            "headline": self.headline,
            "body": self.body,
            "cta": self.cta,
            "layout": self.layout,
            "typography": {"preset": font_preset(self.font_preset)},
            "brand": self.brand(),
        }


def font_preset(value: object) -> str:
    token = str(value or "auto").strip().lower()
    if token not in FONT_PRESETS:
        raise ValueError("editable_ad_font_preset_invalid")
    return token


def _text(value: object, limit: int, *, required: bool = False) -> str:
    token = " ".join(str(value or "").replace("\x00", " ").split()).strip()
    if required and not token:
        raise ValueError("editable_ad_value_required")
    if len(token) > limit or any(ord(c) < 32 for c in token):
        raise ValueError("editable_ad_value_invalid")
    return token


def _brand_json(brand: dict[str, str]) -> str:
    out = {k: str(brand.get(k) or d).strip().upper() for k, d in DEFAULT_BRAND.items()}
    if any(_COLOR.fullmatch(v) is None for v in out.values()):
        raise ValueError("editable_ad_brand_invalid")
    return json.dumps(out, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def eap_replay(facts: list[dict[str, Any]]) -> dict[str, EditableAdProject]:
    out: dict[str, EditableAdProject] = {}
    for f in facts:
        pid = str(f.get("id") or "")
        if f.get("step") == "eap_created":
            out.setdefault(
                pid, EditableAdProject(**{k: f[k] for k in EditableAdProject.__dataclass_fields__ if k in f})
            )
        elif f.get("step") == "eap_set" and pid in out:
            out[pid] = replace(out[pid], **dict(f["set"]), updated_at=f["at"])
    return out


def _iso(now_ms: int) -> str:
    from datetime import UTC, datetime

    return datetime.fromtimestamp(int(now_ms) / 1000, UTC).isoformat(timespec="seconds")


def _set(pid: str, now_ms: int, **changes: Any) -> dict[str, Any]:
    return {"step": "eap_set", "id": pid, "at": _iso(now_ms), "set": changes}


def _editable(publication_status: str | None) -> None:
    if publication_status is None:
        raise ValueError("advertising publication draft was not found")
    if publication_status not in EDITABLE_PUBLICATION_STATES:
        raise ValueError("advertising publication can no longer be edited")


def get_project(projects: dict[str, EditableAdProject], member: str, project_id: str) -> EditableAdProject:
    """Donor get_editable_ad_project: another member's project is indistinguishable from a missing one."""
    value = projects.get(str(project_id or "").strip().lower())
    if value is None or value.member_id != member:
        raise LookupError("editable advertising project was not found")
    return value


def create_project(
    projects: dict[str, EditableAdProject],
    member: str,
    *,
    publication_job_id: str,
    publication_status: str | None,
    kind: str,
    headline: str,
    body: str,
    brand: dict[str, str],
    cta: str = "Записаться",
    layout: str = "lower_card",
    preset: str = "auto",
    now_ms: int,
) -> tuple[EditableAdProject, list[dict[str, Any]]]:
    _editable(publication_status)
    visual_kind = str(kind or "").strip().lower()
    if visual_kind not in {"image", "video"}:
        raise ValueError("editable_ad_kind_invalid")
    for p in projects.values():
        if (p.member_id, p.publication_job_id, p.kind) == (member, publication_job_id, visual_kind):
            return p, []
    lay = str(layout or "lower_card").strip().lower()
    if lay not in LAYOUTS:
        raise ValueError("editable_ad_layout_invalid")
    at = _iso(now_ms)
    seed = f"eap|{member}|{publication_job_id}|{visual_kind}"
    fact = {
        "step": "eap_created",
        "id": str(uuid.UUID(hashlib.sha256(seed.encode()).hexdigest()[:32])),
        "member_id": member,
        "publication_job_id": publication_job_id,
        "kind": visual_kind,
        "headline": _text(headline, 160, required=True),
        "body": _text(body, 500, required=True),
        "cta": _text(cta, 80),
        "layout": lay,
        "font_preset": font_preset(preset),
        "brand_json": _brand_json(brand),
        "created_at": at,
        "updated_at": at,
    }
    return eap_replay([fact])[fact["id"]], [fact]


def prepare_source(
    projects: dict[str, EditableAdProject], member: str, project_id: str, *, publication_status: str | None, now_ms: int
) -> tuple[EditableAdProject, list[dict[str, Any]]]:
    value = get_project(projects, member, project_id)
    _editable(publication_status)
    if value.status == "draft" and not value.source_job_id:
        return value, []
    if value.status != "source_expired":
        raise ValueError("editable_ad_source_rotation_not_allowed")
    ch = {"source_job_id": "", "status": "draft", "revision": value.revision + 1}
    return replace(value, **ch), [_set(value.id, now_ms, **ch)]


def advance_failed_source(
    projects: dict[str, EditableAdProject], member: str, project_id: str, *, now_ms: int
) -> tuple[EditableAdProject, list[dict[str, Any]]]:
    """Rotate only after a definitive failed provider job; ambiguous failures keep the same revision."""
    value = get_project(projects, member, project_id)
    if value.status != "draft" or value.source_job_id:
        return value, []
    ch = {"revision": value.revision + 1}
    return replace(value, **ch), [_set(value.id, now_ms, **ch)]


def bind_source(
    projects: dict[str, EditableAdProject],
    member: str,
    project_id: str,
    source_job_id: str,
    *,
    publication_status: str | None,
    now_ms: int,
) -> tuple[EditableAdProject, list[dict[str, Any]]]:
    value = get_project(projects, member, project_id)
    _editable(publication_status)
    job = _text(source_job_id, 128, required=True)
    if value.source_job_id:
        if value.source_job_id == job and value.status in {"source_ready", "finished"}:
            return value, []
        raise ValueError("editable_ad_source_rebind_forbidden")
    if value.status != "draft":
        raise ValueError("editable_ad_source_state_invalid")
    ch = {"source_job_id": job, "status": "source_ready"}
    return replace(value, **ch), [_set(value.id, now_ms, **ch)]


def update_composition(
    projects: dict[str, EditableAdProject],
    member: str,
    project_id: str,
    *,
    publication_status: str | None,
    now_ms: int,
    headline: str | None = None,
    body: str | None = None,
    cta: str | None = None,
    layout: str | None = None,
    preset: str | None = None,
) -> tuple[EditableAdProject, list[dict[str, Any]]]:
    value = get_project(projects, member, project_id)
    _editable(publication_status)
    lay = value.layout if layout is None else str(layout).strip().lower()
    if lay not in LAYOUTS:
        raise ValueError("editable_ad_layout_invalid")
    ch = {
        "headline": value.headline if headline is None else _text(headline, 160, required=True),
        "body": value.body if body is None else _text(body, 500, required=True),
        "cta": value.cta if cta is None else _text(cta, 80),
        "layout": lay,
        "font_preset": value.font_preset if preset is None else font_preset(preset),
        "status": "source_ready"
        if value.status in {"source_ready", "finished"} and value.source_job_id
        else value.status,
        "revision": value.revision + 1,
    }
    return replace(value, **ch), [_set(value.id, now_ms, **ch)]


def mark_expired(
    projects: dict[str, EditableAdProject], member: str, project_id: str, *, expected_source_job_id: str, now_ms: int
) -> tuple[EditableAdProject, list[dict[str, Any]]]:
    value = get_project(projects, member, project_id)
    expected = _text(expected_source_job_id, 128, required=True)
    if (
        value.source_job_id != expected
        or value.status == "source_expired"
        or value.status not in {"source_ready", "finished"}
    ):
        return value, []
    return replace(value, status="source_expired"), [_set(value.id, now_ms, status="source_expired")]


def finish_project(
    projects: dict[str, EditableAdProject], member: str, project_id: str, *, publication_status: str | None, now_ms: int
) -> tuple[EditableAdProject, list[dict[str, Any]]]:
    value = get_project(projects, member, project_id)
    _editable(publication_status)
    if value.status == "finished" and value.source_job_id:
        return value, []
    if value.status != "source_ready" or not value.source_job_id:
        raise ValueError("editable_ad_project_not_ready")
    return replace(value, status="finished"), [_set(value.id, now_ms, status="finished")]


def render_key(project: EditableAdProject, formats: tuple[str, ...]) -> str:
    payload = json.dumps(
        {
            "project_id": project.id,
            "revision": project.revision,
            "source_job_id": project.source_job_id,
            "composition": project.composition(),
            "formats": list(formats),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return "clientplatform:editable:" + hashlib.sha256(payload.encode()).hexdigest()[:32]


def render_formats(formats: tuple[str, ...] = DEFAULT_FORMATS) -> tuple[str, ...]:
    chosen = tuple(dict.fromkeys(str(item or "").strip().lower() for item in formats))
    if not chosen or len(chosen) > 4:
        raise ValueError("editable_ad_formats_invalid")
    return chosen


def render_check(project: EditableAdProject, *, job_status: str, asset_ready: bool, job_kind: str) -> str:
    """Donor render_editable_ad_project decision on the gateway poll result: "ok" or raises."""
    if not project.source_job_id:
        raise EditableAdSourceExpired("editable_ad_source_missing")
    if job_status == "succeeded" and not asset_ready:
        raise EditableAdSourceExpired("editable_ad_source_expired")
    if job_status != "succeeded" or not asset_ready:
        raise EditableAdError("editable_ad_source_not_ready")
    if job_kind != project.kind:
        raise EditableAdError("editable_ad_source_kind_mismatch")
    return "ok"
