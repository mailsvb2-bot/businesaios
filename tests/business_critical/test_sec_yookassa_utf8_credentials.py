"""YooKassa webhook verifier must compare secrets as bytes (Codex P2 on #528)."""

from __future__ import annotations

import base64
import hashlib
import hmac

import pytest

from core.payments.yookassa_webhook import WebhookAuthError, verify_webhook


def _basic(user: str, password: str) -> dict[str, str]:
    raw = f"{user}:{password}".encode()
    return {"Authorization": "Basic " + base64.b64encode(raw).decode("ascii")}


def test_non_ascii_basic_credentials_are_accepted_exactly() -> None:
    verify_webhook(headers=_basic("shop", "pässwörд"), body_bytes=b"{}", auth_mode="basic",
                   basic_user="shop", basic_pass="pässwörд")


@pytest.mark.parametrize("user,password", [("shop", "passwörд"), ("shöp", "pässwörд"), ("", "")])
def test_non_ascii_basic_mismatch_is_auth_error_not_type_error(user: str, password: str) -> None:
    with pytest.raises(WebhookAuthError):
        verify_webhook(headers=_basic(user, password), body_bytes=b"{}", auth_mode="basic",
                       basic_user="shop", basic_pass="pässwörд")


def test_basic_header_with_non_base64_garbage_is_rejected() -> None:
    with pytest.raises(WebhookAuthError):
        verify_webhook(headers={"Authorization": "Basic !!!not-base64!!!"}, body_bytes=b"{}",
                       auth_mode="basic", basic_user="shop", basic_pass="secret")


def test_non_ascii_signature_header_is_auth_error_not_type_error() -> None:
    with pytest.raises(WebhookAuthError):
        verify_webhook(headers={"X-YK-Signature": "подпись"}, body_bytes=b"{}",
                       auth_mode="hmac_sha256", hmac_secret="s")


def test_hmac_signature_still_binds_exact_body() -> None:
    body = b'{"event":"payment.succeeded"}'
    sig = hmac.new(b"s", body, hashlib.sha256).hexdigest()
    verify_webhook(headers={"X-YK-Signature": sig.upper()}, body_bytes=body, auth_mode="hmac_sha256", hmac_secret="s")
    with pytest.raises(WebhookAuthError):
        verify_webhook(headers={"X-YK-Signature": sig}, body_bytes=body + b" ", auth_mode="hmac_sha256", hmac_secret="s")
