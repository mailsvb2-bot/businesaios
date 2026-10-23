"""Website brand discovery (port of donor application/visual_brand_discovery).

Pure: parses HTML into a brand suggestion fact. Network is injected (``fetch``) and every
hop is validated as a public http(s) URL on ports 80/443 with globally routable DNS, so the
module itself opens no sockets. Logos are evidence only and are never persisted.
"""

from __future__ import annotations

import ipaddress
import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

MAX_HTML = 524_288
MAX_REDIRECTS = 3
_COLOR = re.compile(r"#[0-9A-Fa-f]{6}")
_VAR = re.compile(r"--(?P<n>[A-Za-z0-9_-]*(?:brand|primary|accent|secondary|text)[A-Za-z0-9_-]*)\s*:\s*(?P<c>#[0-9A-Fa-f]{6})", re.I)
_LD_TYPES = frozenset({"organization", "localbusiness", "professionalservice"})
_VOCAB = (
    (("минимал", "minimal"), "minimal"), (("современ", "modern"), "modern"),
    (("преми", "premium", "luxury"), "premium"), (("спокой", "calm", "gentle"), "calm"),
    (("натурал", "natural", "organic"), "natural"), (("технолог", "tech", "digital"), "technology"),
    (("эксперт", "expert", "professional"), "expert"), (("дружелюб", "friendly", "human"), "human"),
)
FIELDS = ("display_name", "visual_keywords", "primary_color", "accent_color", "text_color")


class BrandDiscoveryError(ValueError):
    pass


@dataclass(frozen=True)
class Brand:
    business_id: str
    display_name: str = ""
    visual_keywords: tuple[str, ...] = ()
    primary_color: str | None = None
    accent_color: str | None = None
    text_color: str | None = None


class _Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.names: list[str] = []
        self.themes: list[str] = []
        self.logos: list[str] = []
        self.styles: list[str] = []
        self.meta: list[str] = []
        self._style = self._ld = 0
        self._ld_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        v = {str(k).strip().lower(): str(x or "").strip() for k, x in attrs if k}
        t = tag.lower()
        if t == "style":
            self._style += 1
        elif t == "script" and v.get("type", "").lower() == "application/ld+json":
            self._ld, self._ld_parts = self._ld + 1, []
        elif t == "meta":
            key, content = (v.get("property") or v.get("name") or "").lower(), v.get("content", "")
            if content:
                if key in {"og:site_name", "application-name"}:
                    self.names.append(content)
                elif key == "theme-color":
                    self.themes.append(content)
                elif key in {"description", "og:description", "keywords"}:
                    self.meta.append(content)
                elif key in {"logo", "og:logo"}:
                    self.logos.append(content)
        elif t == "link":
            if "logo" in {p.casefold() for p in v.get("rel", "").split()} and v.get("href"):
                self.logos.append(v["href"])
        else:
            if t == "img" and v.get("src") and "logo" in " ".join(v.get(n, "") for n in ("id", "class", "alt", "aria-label")).casefold():
                self.logos.append(v["src"])
            if v.get("style"):
                self.styles.append(v["style"])

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t == "style" and self._style:
            self._style -= 1
        elif t == "script" and self._ld:
            self._ld -= 1
            if not self._ld and self._ld_parts:
                self._json_ld("".join(self._ld_parts))
                self._ld_parts = []

    def handle_data(self, data: str) -> None:
        if self._style:
            self.styles.append(data)
        elif self._ld:
            self._ld_parts.append(data)

    def _json_ld(self, raw: str) -> None:
        try:
            payload = json.loads(raw)
        except ValueError:
            return
        for item in _walk(payload):
            kind = item.get("@type")
            kinds = {str(kind).casefold()} if isinstance(kind, str) else {str(k).casefold() for k in kind} if isinstance(kind, list) else set()
            if kinds & _LD_TYPES:
                if str(item.get("name") or "").strip():
                    self.names.append(str(item["name"]).strip())
                logo = item.get("logo")
                logo = logo.get("url") if isinstance(logo, dict) else logo
                if isinstance(logo, str) and logo.strip():
                    self.logos.append(logo.strip())


def _walk(value: object) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for c in value.values():
            yield from _walk(c)
    elif isinstance(value, list):
        for c in value:
            yield from _walk(c)


def _color(value: object) -> str | None:
    token = str(value or "").strip().upper()
    return token if _COLOR.fullmatch(token) else None


def normalize_url(raw: str) -> str:
    """http(s) only, no credentials, ports 80/443, IDNA host, no fragment."""
    token = str(raw or "").strip()
    if not token:
        raise BrandDiscoveryError("brand_website_url_required")
    try:
        p = urlsplit(token)
        port = p.port
    except ValueError as exc:
        raise BrandDiscoveryError("brand_website_url_invalid") from exc
    scheme = p.scheme.lower()
    if scheme not in {"http", "https"} or not p.hostname:
        raise BrandDiscoveryError("brand_website_url_must_be_http")
    if p.username is not None or p.password is not None:
        raise BrandDiscoveryError("brand_website_credentials_forbidden")
    if (port or (443 if scheme == "https" else 80)) not in {80, 443}:
        raise BrandDiscoveryError("brand_website_nonstandard_port_forbidden")
    try:
        host = p.hostname.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise BrandDiscoveryError("brand_website_hostname_invalid") from exc
    netloc = f"[{host}]" if ":" in host else host
    if port and port != (443 if scheme == "https" else 80):
        netloc = f"{netloc}:{port}"
    return urlunsplit((scheme, netloc, quote(p.path or "/", safe="/:@-._~!$&'()*+,;=%"), quote(p.query, safe="/?:@-._~!$'()*+,;=&%"), ""))


def validate_public(url: str, resolve: Callable[[str], Iterable[str]]) -> str:
    """Normalized URL whose host resolves only to globally routable addresses."""
    norm = normalize_url(url)
    host = str(urlsplit(norm).hostname or "")
    try:
        addrs = sorted(set(resolve(host)))
    except OSError as exc:
        raise BrandDiscoveryError("brand_website_dns_failed") from exc
    if not addrs:
        raise BrandDiscoveryError("brand_website_dns_empty")
    for a in addrs:
        try:
            ok = ipaddress.ip_address(a).is_global
        except ValueError as exc:
            raise BrandDiscoveryError("brand_website_dns_invalid") from exc
        if not ok:
            raise BrandDiscoveryError("brand_website_private_address_forbidden")
    return norm


def fetch_html(url: str, *, fetch: Callable[[str], tuple[int, dict[str, str], bytes]], resolve: Callable[[str], Iterable[str]]) -> tuple[str, str]:
    """(final_url, text). ``fetch`` is the injected transport; redirects are re-validated."""
    current = str(url or "").strip()
    for hop in range(MAX_REDIRECTS + 1):
        target = validate_public(current, resolve)
        status, raw_headers, body = fetch(target)
        headers = {str(k).lower(): str(v) for k, v in raw_headers.items()}
        if status in {301, 302, 303, 307, 308}:
            loc = headers.get("location", "").strip()
            if hop >= MAX_REDIRECTS or not loc:
                raise BrandDiscoveryError("brand_website_too_many_redirects" if loc else "brand_website_redirect_without_location")
            current = urljoin(target, loc)
            continue
        if status != 200:
            raise BrandDiscoveryError("brand_website_http_status")
        if len(body) > MAX_HTML:
            raise BrandDiscoveryError("brand_website_too_large")
        if headers.get("content-encoding", "").strip().lower() not in {"", "identity"}:
            raise BrandDiscoveryError("brand_website_encoding_unsupported")
        ctype = headers.get("content-type", "").strip().lower()
        if not ctype.startswith(("text/html", "application/xhtml+xml")):
            raise BrandDiscoveryError("brand_website_html_required")
        m = re.search(r"charset=([A-Za-z0-9._-]+)", ctype)
        try:
            return target, body.decode(m.group(1) if m else "utf-8", errors="replace")
        except LookupError as exc:
            raise BrandDiscoveryError("brand_website_charset_invalid") from exc
    raise BrandDiscoveryError("brand_website_too_many_redirects")


def _pick(named: dict[str, str], words: tuple[str, ...]) -> str | None:
    return next((c for n, c in named.items() if any(w in n for w in words)), None)


def keywords(text: str) -> tuple[str, ...]:
    f = text.casefold()
    return tuple(label for needles, label in _VOCAB if any(n in f for n in needles))[:6]


def suggest(*, business_id: str, source_url: str, html: str, current: Brand | None = None) -> dict[str, Any]:
    """``brand_suggested`` fact: proposal only, the owner confirms before anything is saved."""
    base = current or Brand(business_id=business_id)
    if base.business_id != business_id:
        raise BrandDiscoveryError("brand_business_mismatch")
    url = normalize_url(source_url)
    p = _Parser()
    p.feed(str(html or "")[:MAX_HTML])
    named: dict[str, str] = {}
    for m in _VAR.finditer("\n".join(p.styles)):
        named.setdefault(m.group("n").casefold(), m.group("c").upper())
    theme = next((c for c in map(_color, p.themes) if c), None)
    name = next((" ".join(n.split())[:120] for n in p.names if n.split()), "") or base.display_name
    found = keywords(" ".join(p.meta))
    brand = replace(
        base,
        display_name=name,
        visual_keywords=tuple(dict.fromkeys((*base.visual_keywords, *found)))[:12],
        primary_color=theme or _pick(named, ("primary", "brand")) or base.primary_color,
        accent_color=_pick(named, ("accent", "secondary")) or base.accent_color,
        text_color=_pick(named, ("text", "foreground", "on-primary")) or base.text_color,
    )
    evidence = [k for k, hit in (("site_name", name != base.display_name), ("theme_color", bool(theme)),
                ("css_brand_variables", bool(named)), ("site_metadata", bool(found)), ("logo_reference_detected", bool(p.logos))) if hit]
    changed = [f for f in FIELDS if getattr(base, f) != getattr(brand, f)]
    return {
        "step": "brand_suggested", "business_id": business_id, "source_url": url,
        "brand": {f: (list(getattr(brand, f)) if f == "visual_keywords" else getattr(brand, f)) for f in FIELDS},
        "changed_fields": changed, "evidence": evidence, "has_changes": bool(changed),
    }


def discover(*, business_id: str, website_url: str, fetch: Callable[[str], tuple[int, dict[str, str], bytes]],
             resolve: Callable[[str], Iterable[str]], current: Brand | None = None) -> dict[str, Any]:
    final, html = fetch_html(website_url, fetch=fetch, resolve=resolve)
    return suggest(business_id=business_id, source_url=final, html=html, current=current)
