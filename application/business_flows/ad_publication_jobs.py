"""Ad publication jobs + managed campaigns (port of clientplatform ad_connections worker
paths and ad_goal_publication).

State is replayed from facts; every provider interaction goes through an injected
``DirectProvider``. The default ``DryRunDirectProvider`` is an in-memory simulator: it
never touches the network and never enables a campaign, so nothing can spend money.
Managed campaigns are created *disabled*; a submitted job is a provider DRAFT ad. Spend
remains gated by ``ad_proposals.publish_decision`` + ``ad_spend_guard``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any, Protocol, TypeVar

from application.business_flows.ad_media import Asset

T = TypeVar("T")
ACCOUNT_ATTENTION_ERRORS = frozenset(
    {"provider_http_401", "provider_53", "provider_54", "provider_55", "provider_56",
     "provider_invalid_token", "provider_unauthorized", "oauth_refresh_token_missing"}
)


class DirectError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool = False) -> None:
        super().__init__(code)
        self.code, self.retryable = code, retryable


class Busy(DirectError):
    def __init__(self, msg: str) -> None:
        super().__init__(msg)


class DirectProvider(Protocol):
    def refresh(self, token: dict[str, str]) -> dict[str, str]: ...
    def find_managed_campaign(self, access_token: str, campaign_name: str) -> str | None: ...
    def create_disabled_managed_campaign(self, access_token: str, campaign_name: str) -> str: ...
    def publish_text_ad(self, access_token: str, job: Job, managed_name: str | None) -> tuple[str, str]: ...
    def update_copy(self, access_token: str, ad_id: str, job: Job) -> None: ...
    def clear_media(self, access_token: str, ad_id: str) -> None: ...
    def attach_image(self, access_token: str, ad_id: str, image_hash: str) -> None: ...
    def video_status(self, access_token: str, video_id: str) -> str: ...
    def create_video_extension(self, access_token: str, video_id: str) -> str: ...
    def attach_video(self, access_token: str, ad_id: str, creative_id: str) -> None: ...


@dataclass
class DryRunDirectProvider:
    """Deterministic simulator; records calls. No network, campaigns never enabled."""

    calls: list[tuple[str, ...]] = field(default_factory=list)
    campaigns: dict[str, str] = field(default_factory=dict)
    video: dict[str, str] = field(default_factory=dict)

    def _id(self, *parts: str) -> str:
        return "dry-" + hashlib.sha256(":".join(parts).encode()).hexdigest()[:12]

    def refresh(self, token: dict[str, str]) -> dict[str, str]:
        self.calls.append(("refresh",))
        return {**token, "access_token": "dry-refreshed"}

    def find_managed_campaign(self, access_token: str, campaign_name: str) -> str | None:
        self.calls.append(("find", campaign_name))
        return self.campaigns.get(campaign_name)

    def create_disabled_managed_campaign(self, access_token: str, campaign_name: str) -> str:
        self.calls.append(("create_disabled", campaign_name))
        return self.campaigns.setdefault(campaign_name, self._id("cmp", campaign_name))

    def publish_text_ad(self, access_token: str, job: Job, managed_name: str | None) -> tuple[str, str]:
        self.calls.append(("publish_draft", job.job_id, managed_name or ""))
        return self._id("grp", job.idempotency_key), self._id("ad", job.idempotency_key)

    def update_copy(self, access_token: str, ad_id: str, job: Job) -> None:
        self.calls.append(("update_copy", ad_id))

    def clear_media(self, access_token: str, ad_id: str) -> None:
        self.calls.append(("clear_media", ad_id))

    def attach_image(self, access_token: str, ad_id: str, image_hash: str) -> None:
        self.calls.append(("attach_image", ad_id, image_hash))

    def video_status(self, access_token: str, video_id: str) -> str:
        return self.video.get(video_id, "READY")

    def create_video_extension(self, access_token: str, video_id: str) -> str:
        self.calls.append(("video_extension", video_id))
        return self._id("cr", video_id)

    def attach_video(self, access_token: str, ad_id: str, creative_id: str) -> None:
        self.calls.append(("attach_video", ad_id, creative_id))


@dataclass
class Session:
    """Port of ad_provider_session.with_access_token / _refresh_token_bundle: one refresh on auth errors."""

    provider: DirectProvider
    token: dict[str, str]
    refreshed: dict[str, str] | None = None

    def call(self, op: Callable[[str], T]) -> T:
        try:
            return op(self.token["access_token"])
        except DirectError as exc:
            if exc.code not in ACCOUNT_ATTENTION_ERRORS or not self.token.get("refresh_token"):
                raise
            self.token = self.refreshed = self.provider.refresh(self.token)
            return op(self.token["access_token"])


@dataclass(frozen=True)
class Managed:
    key: str
    promotion_id: str
    connection_id: str
    name: str
    status: str  # provisioning | ready | failed
    external_campaign_id: str = ""
    error: str = ""
    version: int = 0


@dataclass(frozen=True)
class Job:
    job_id: str
    promotion_id: str
    connection_id: str
    external_campaign_id: str
    region_ids: tuple[int, ...]
    title: str
    text: str
    source_url: str
    status: str = "queued"  # queued | publishing | submitted | failed
    attempts: int = 0
    lock: str = ""
    ad_group_id: str = ""
    ad_id: str = ""
    error: str = ""

    @property
    def idempotency_key(self) -> str:
        return hashlib.sha256(f"{self.job_id}:{self.external_campaign_id}".encode()).hexdigest()[:32]


@dataclass
class Ledger:
    managed: dict[str, Managed] = field(default_factory=dict)
    jobs: dict[str, Job] = field(default_factory=dict)


def managed_key(business_id: str, promotion_id: str, connection_id: str) -> str:
    return hashlib.sha256(f"{business_id}:{promotion_id}:{connection_id}".encode()).hexdigest()[:20]


def managed_name(key: str) -> str:
    return f"BAI managed {key[:12]}"


def replay(payloads: list[dict[str, Any]]) -> Ledger:
    led = Ledger()
    for p in payloads:
        s = p.get("step")
        m = led.managed.get(p.get("key", ""))
        j = led.jobs.get(p.get("job_id", ""))
        if s == "ad_managed_reserved" and m is None:
            led.managed[p["key"]] = Managed(p["key"], p["promotion_id"], p["connection_id"], p["name"], "provisioning")
        elif s == "ad_managed_bound" and m and m.status != "ready":
            if any(o.external_campaign_id == p["external_campaign_id"] and o.key != m.key for o in led.managed.values()):
                continue  # donor IntegrityError: one external campaign per promotion
            led.managed[m.key] = replace(m, status="ready", external_campaign_id=p["external_campaign_id"], error="", version=m.version + 1)
        elif s == "ad_managed_failed" and m and m.status != "ready":
            led.managed[m.key] = replace(m, status="provisioning" if p.get("uncertain") else "failed", error=p["error"], version=m.version + 1)
        elif s == "ad_managed_reclaimed" and m and m.status == "failed" and p.get("version") == m.version:
            led.managed[m.key] = replace(m, status="provisioning", error="", version=m.version + 1)
        elif s == "ad_job_queued" and j is None:
            led.jobs[p["job_id"]] = Job(p["job_id"], p["promotion_id"], p["connection_id"], p["external_campaign_id"],
                                        tuple(p["region_ids"]), p["title"], p["text"], p["source_url"])
        elif j is None:
            continue
        elif s == "ad_job_claimed" and j.status == "queued":
            led.jobs[j.job_id] = replace(j, status="publishing", lock=p["lock"], attempts=j.attempts + 1)
        elif s == "ad_job_failed" and j.status == "publishing" and p["lock"] == j.lock:
            led.jobs[j.job_id] = replace(j, status="queued" if p["retry"] else "failed", lock="", error=p["error"])
        elif s == "ad_job_submitted" and j.status == "publishing" and p["lock"] == j.lock:
            led.jobs[j.job_id] = replace(j, status="submitted", lock="", ad_group_id=p["ad_group_id"], ad_id=p["ad_id"], error="")
    return led


def ensure_managed_campaign(led: Ledger, sess: Session, *, business_id: str, promotion_id: str,
                            connection_id: str) -> tuple[Managed, list[dict[str, Any]]]:
    """Port of ensure_yandex_managed_campaign (+ _reserve/_claim_failed/_bind/_mark_*). Returns (state, facts)."""
    key = managed_key(business_id, promotion_id, connection_id)
    facts: list[dict[str, Any]] = []
    cur = led.managed.get(key)
    created = cur is None
    if created:
        facts.append({"step": "ad_managed_reserved", "key": key, "promotion_id": promotion_id,
                      "connection_id": connection_id, "name": managed_name(key)})
        cur = Managed(key, promotion_id, connection_id, managed_name(key), "provisioning")
    if cur.status == "ready":
        return cur, facts

    def fail(exc: BaseException, uncertain: bool) -> None:
        code = exc.code if isinstance(exc, DirectError) else "provider_refresh_failure"
        facts.append({"step": "ad_managed_failed", "key": key, "error": code[:64], "uncertain": uncertain})

    def bind(ext: str) -> Managed:
        if not ext or any(o.external_campaign_id == ext and o.key != key for o in led.managed.values()):
            raise DirectError("external campaign is already bound to another promotion")
        facts.append({"step": "ad_managed_bound", "key": key, "external_campaign_id": ext})
        return replace(cur, status="ready", external_campaign_id=ext)

    try:
        found = sess.call(lambda t: sess.provider.find_managed_campaign(t, cur.name))
    except DirectError as exc:
        fail(exc, False)
        exc.facts = facts  # type: ignore[attr-defined]
        raise
    if found:
        return bind(found), facts
    if not created:
        if cur.status != "failed":
            raise Busy("managed campaign provisioning is already in progress")
        facts.append({"step": "ad_managed_reclaimed", "key": key, "version": cur.version})
    try:
        ext = sess.call(lambda t: sess.provider.create_disabled_managed_campaign(t, cur.name))
    except DirectError as exc:
        fail(exc, exc.retryable)
        exc.facts = facts  # type: ignore[attr-defined]
        raise
    return bind(ext), facts


def queue_job(led: Ledger, *, promotion_id: str, connection_id: str, external_campaign_id: str,
              region_ids: tuple[int, ...], title: str, text: str, source_url: str) -> dict[str, Any] | None:
    """Port of create_ad_publication_draft: create-or-get (idempotent on content)."""
    jid = "adjob-" + hashlib.sha256(f"{promotion_id}:{connection_id}:{external_campaign_id}:{title}:{text}:{source_url}".encode()).hexdigest()[:16]
    if jid in led.jobs:
        return None
    return {"step": "ad_job_queued", "job_id": jid, "promotion_id": promotion_id, "connection_id": connection_id,
            "external_campaign_id": external_campaign_id, "region_ids": list(region_ids), "title": title,
            "text": text, "source_url": source_url}


def queue_managed_job(led: Ledger, sess: Session, *, business_id: str, promotion_id: str, connection_id: str,
                      region_ids: tuple[int, ...], title: str, text: str, source_url: str) -> list[dict[str, Any]]:
    """Port of create_managed_ad_publication_draft."""
    m, facts = ensure_managed_campaign(led, sess, business_id=business_id, promotion_id=promotion_id, connection_id=connection_id)
    if not m.external_campaign_id:
        raise DirectError("managed campaign is not ready")
    q = queue_job(led, promotion_id=promotion_id, connection_id=connection_id, external_campaign_id=m.external_campaign_id,
                  region_ids=region_ids, title=title, text=text, source_url=source_url)
    return facts + ([q] if q else [])


def _managed_name_for(led: Ledger, job: Job) -> str | None:
    for m in led.managed.values():
        if (m.promotion_id, m.connection_id, m.external_campaign_id, m.status) == (job.promotion_id, job.connection_id, job.external_campaign_id, "ready"):
            return m.name
    return None


def attach_media(sess: Session, job: Job, ad_id: str, asset: Asset | None) -> tuple[tuple[bool, bool, bool], list[dict[str, Any]]]:
    """Port of ad_goal_publication._attach_media -> ((attached, pending, failed), facts)."""
    p = sess.provider

    def clear() -> None:
        sess.call(lambda t: p.clear_media(t, ad_id))

    def err(code: str) -> tuple[tuple[bool, bool, bool], list[dict[str, Any]]]:
        clear()
        return (False, False, True), [{"step": "ad_media_provider_error", "job_id": job.job_id, "error": code}]

    if asset is None:
        clear()
        return (False, False, False), []
    if asset.state == "uploading":
        clear()
        return (False, True, False), []
    if asset.state != "ready" or asset.error:
        clear()
        return (False, False, True), []
    if asset.kind == "image":
        if not asset.image_hash:
            return err("ad_image_reference_missing")
        sess.call(lambda t: p.attach_image(t, ad_id, asset.image_hash))
        return (True, False, False), []
    if not asset.video_id:
        return err("ad_video_reference_missing")
    status = sess.call(lambda t: p.video_status(t, asset.video_id))
    if status == "ERROR":
        return err("ad_video_processing_failed")
    if status in {"NEW", "CONVERTING"}:
        clear()  # spend stays blocked until READY
        return (False, True, False), []
    facts: list[dict[str, Any]] = []
    creative = asset.creative_id
    if not creative:
        creative = sess.call(lambda t: p.create_video_extension(t, asset.video_id))
        facts.append({"step": "ad_media_provider_ids", "job_id": job.job_id, "creative_id": creative})
    sess.call(lambda t: p.attach_video(t, ad_id, creative))
    return (True, False, False), facts


@dataclass
class Outcome:
    job: Job | None
    facts: list[dict[str, Any]]
    media: tuple[bool, bool, bool] = (False, False, False)


def _lock(job: Job) -> str:
    return f"lock-{job.job_id}-{job.attempts + 1}"


def submit(led: Ledger, sess: Session, job_id: str, asset: Asset | None, *, max_attempts: int = 5) -> Outcome:
    """Port of submit_goal_publication / process_one_ad_publication / _publish_job / _fail_claimed_job.

    queued -> claim -> provider DRAFT ad -> copy sync -> media; already-submitted -> media re-sync.
    """
    job = led.jobs.get(job_id)
    if job is None:
        raise DirectError("advertising draft not found")
    if job.status == "submitted":
        try:
            sess.call(lambda t: sess.provider.update_copy(t, job.ad_id, job))
            media, facts = attach_media(sess, job, job.ad_id, asset)
        except (DirectError, OSError, ValueError, TypeError) as exc:
            raise DirectError("provider_media_sync_failure") from exc
        return Outcome(job, facts, media)
    if job.status != "queued":
        raise Busy("advertising draft is already being processed")
    lock = _lock(job)
    facts: list[dict[str, Any]] = [{"step": "ad_job_claimed", "job_id": job_id, "lock": lock}]
    try:
        grp, ad = sess.call(lambda t: sess.provider.publish_text_ad(t, job, _managed_name_for(led, job)))
        sess.call(lambda t: sess.provider.update_copy(t, ad, job))
        media, mfacts = attach_media(sess, job, ad, asset)
    except DirectError as exc:
        retry = exc.retryable and job.attempts + 1 < max_attempts
        facts.append({"step": "ad_job_failed", "job_id": job_id, "lock": lock, "error": exc.code[:64], "retry": retry,
                      "keep_connection": exc.code not in ACCOUNT_ATTENTION_ERRORS})
        return Outcome(None, facts)
    except (OSError, ValueError, TypeError):
        facts.append({"step": "ad_job_failed", "job_id": job_id, "lock": lock, "error": "provider_runtime_failure", "retry": False,
                      "keep_connection": True})
        return Outcome(None, facts)
    facts += [{"step": "ad_job_submitted", "job_id": job_id, "lock": lock, "ad_group_id": grp, "ad_id": ad}, *mfacts]
    return Outcome(replace(job, status="submitted", ad_group_id=grp, ad_id=ad), facts, media)


def process_one(led: Ledger, sess_for: Callable[[Job], Session], assets: dict[str, Asset], *, max_attempts: int = 5) -> Outcome | None:
    """Port of process_one_ad_publication: oldest queued job only."""
    due = next((j for j in led.jobs.values() if j.status == "queued"), None)
    return None if due is None else submit(led, sess_for(due), due.job_id, assets.get(due.job_id), max_attempts=max_attempts)


def process_pending_video(led: Ledger, sess_for: Callable[[Job], Session], assets: dict[str, Asset]) -> list[dict[str, Any]] | None:
    """Port of process_one_pending_video_asset: finish one video extension after conversion."""
    def eligible(j: Job) -> bool:
        a = assets.get(j.job_id)
        return bool(j.status == "submitted" and j.ad_id and a and a.kind == "video" and a.video_id
                    and not a.creative_id and not a.error)

    j = next((x for x in led.jobs.values() if eligible(x)), None)
    if j is None:
        return None
    a, sess = assets[j.job_id], sess_for(j)
    try:
        status = sess.call(lambda t: sess.provider.video_status(t, a.video_id))
    except DirectError:
        return None
    if status == "ERROR":
        try:
            sess.call(lambda t: sess.provider.clear_media(t, j.ad_id))
        except DirectError:
            return None
        return [{"step": "ad_media_provider_error", "job_id": j.job_id, "error": "ad_video_processing_failed"}]
    if status != "READY":
        return []
    cr = sess.call(lambda t: sess.provider.create_video_extension(t, a.video_id))
    sess.call(lambda t: sess.provider.attach_video(t, j.ad_id, cr))
    return [{"step": "ad_media_provider_ids", "job_id": j.job_id, "creative_id": cr}]
