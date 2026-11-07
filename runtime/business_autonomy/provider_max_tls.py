"""Pinned additional trust for MAX, without changing process-global TLS policy."""
from __future__ import annotations

import hashlib
import os
import ssl
from pathlib import Path
from urllib.parse import urlsplit

# Official Russian Trusted Root CA, verified against the publicly published certificate.
_ROOT_CERT_SHA256 = "d26d2d0231b7c39f92cc738512ba54103519e4405d68b5bd703e9788ca8ecf31"


def max_tls_ca_file(url: str) -> str | None:
    """Only trust a verified additional CA for the exact official MAX API origin."""
    path = str(os.environ.get("BUSINESAIOS_MAX_CA_FILE") or "").strip()
    if not path:
        return None  # standard system trust remains in force
    parsed = urlsplit(url)
    if (parsed.scheme, parsed.hostname, parsed.port) != ("https", "platform-api2.max.ru", None):
        raise ValueError("max_tls_ca_origin_denied")
    cert_path = Path(path)
    if not cert_path.is_file():
        raise ValueError("max_tls_ca_file_missing")
    raw = cert_path.read_text(encoding="ascii")
    if raw.count("-----BEGIN CERTIFICATE-----") != 1 or raw.count("-----END CERTIFICATE-----") != 1:
        raise ValueError("max_tls_ca_single_root_required")
    try:
        fingerprint = hashlib.sha256(ssl.PEM_cert_to_DER_cert(raw)).hexdigest()
    except (ValueError, UnicodeError) as exc:
        raise ValueError("max_tls_ca_invalid_pem") from exc
    if fingerprint != _ROOT_CERT_SHA256:
        raise ValueError("max_tls_ca_untrusted_fingerprint")
    return str(cert_path)


__all__ = ["max_tls_ca_file"]
