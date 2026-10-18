"""Fail-closed admission of existing ClientPlatform bot identities to BusinessAIOS.

This is a pure cutover safety contract, not a second connection registry or
deployment mechanism. Existing ProviderAdmin and ProviderWebhookReconciler own
secret storage, route binding, and registration. No credential values are logged.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

CHANNELS = ("telegram_bot", "vk_messaging", "max_messaging")


@dataclass(frozen=True)
class ChannelTransferEvidence:
    provider_key: str
    account_identity: str
    legacy_worker_stopped: bool
    legacy_polling_stopped: bool
    new_credential_in_vault: bool
    new_ingress_ready: bool
    callback_url: str
    ownership_confirmed: bool


def check_cutover_admission(
    evidence: tuple[ChannelTransferEvidence, ...], *,
    expected_callback_host: str,
) -> dict[str, object]:
    """Allow switching only after the donor is quiesced and receiver can answer.

    Identity is the existing provider bot/group identifier, never a newly issued
    token or changed bot name. Evidence must come from real operational probes,
    not from configuration guesses or passing unit tests.
    """
    problems: list[str] = []
    if not expected_callback_host or expected_callback_host.lower() != expected_callback_host:
        return {"ready": False, "reasons": ("callback_host_invalid",)}
    if len(evidence) != len(CHANNELS) or {e.provider_key for e in evidence} != set(CHANNELS):
        return {"ready": False, "reasons": ("three_unique_provider_evidence_required",)}
    if len({e.account_identity for e in evidence}) != len(CHANNELS):
        problems.append("duplicate_provider_identity")
    for item in evidence:
        name = item.provider_key
        if not item.account_identity.strip() or len(item.account_identity) > 160:
            problems.append(f"{name}:provider_identity_missing")
        for field in (
            "legacy_worker_stopped", "legacy_polling_stopped",
            "new_credential_in_vault", "new_ingress_ready", "ownership_confirmed",
        ):
            if getattr(item, field) is not True:
                problems.append(f"{name}:{field}_not_verified")
        try:
            parts = urlsplit(item.callback_url)
            valid_url = (
                parts.scheme == "https"
                and parts.hostname == expected_callback_host
                and parts.username is None and parts.password is None
                and parts.port is None and not parts.fragment
                and parts.path.endswith("/" + name)
                and "/providers/webhook/" in parts.path
            )
        except ValueError:
            valid_url = False
        if not valid_url:
            problems.append(f"{name}:callback_url_invalid")
    return {"ready": not problems, "reasons": tuple(problems)}
