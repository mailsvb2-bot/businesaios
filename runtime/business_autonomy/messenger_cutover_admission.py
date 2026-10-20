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
    transport_mode: str = "webhook"


def check_cutover_admission(
    evidence: tuple[ChannelTransferEvidence, ...], *,
    expected_callback_host: str,
    selected_providers: tuple[str, ...] = CHANNELS,
) -> dict[str, object]:
    """Allow switching only after the donor is quiesced and receiver can answer.

    Selected providers can be transferred one by one; the default still requires
    all three. Each selected provider requires its own real evidence.
    Identity is the existing provider bot/group identifier, never a newly issued
    token or changed bot name. Evidence must come from real operational probes,
    not from configuration guesses or passing unit tests.
    """
    problems: list[str] = []
    # Validate the expected host as a DNS authority, not merely a string.
    # This value is compared with urlsplit().hostname for webhook channels.
    if (not isinstance(expected_callback_host, str)
            or not expected_callback_host
            or expected_callback_host.lower() != expected_callback_host
            or any(ch.isspace() or ch in "/?#@:[]" for ch in expected_callback_host)):
        return {"ready": False, "reasons": ("callback_host_invalid",)}
    try:
        if urlsplit("https://" + expected_callback_host).hostname != expected_callback_host:
            return {"ready": False, "reasons": ("callback_host_invalid",)}
    except ValueError:
        return {"ready": False, "reasons": ("callback_host_invalid",)}
    if (not selected_providers or len(set(selected_providers)) != len(selected_providers)
            or not set(selected_providers).issubset(CHANNELS)):
        return {"ready": False, "reasons": ("selected_providers_invalid",)}
    if (len(evidence) != len(selected_providers)
            or {e.provider_key for e in evidence} != set(selected_providers)):
        return {"ready": False, "reasons": ("exact_selected_provider_evidence_required",)}
    if len({e.account_identity for e in evidence}) != len(evidence):
        problems.append("duplicate_provider_identity")
    for item in evidence:
        name = item.provider_key
        if (not isinstance(item.account_identity, str)
                or not item.account_identity.strip()
                or len(item.account_identity) > 160):
            problems.append(f"{name}:provider_identity_missing")
        for field in (
            "legacy_worker_stopped", "legacy_polling_stopped",
            "new_credential_in_vault", "new_ingress_ready", "ownership_confirmed",
        ):
            if getattr(item, field) is not True:
                problems.append(f"{name}:{field}_not_verified")
        if item.transport_mode == "long_polling" and name == "telegram_bot":
            # A polling connector must not claim a webhook route. The operational
            # evidence above still requires verified donor shutdown and ingress.
            if item.callback_url:
                problems.append(f"{name}:polling_callback_must_be_empty")
            continue
        if item.transport_mode != "webhook":
            problems.append(f"{name}:transport_mode_invalid")
            continue
        try:
            parts = urlsplit(item.callback_url)
            valid_url = (
                parts.scheme == "https"
                and parts.hostname == expected_callback_host
                and parts.username is None and parts.password is None
                and parts.port is None and not parts.query and not parts.fragment
                and parts.path.endswith("/" + name)
                and "/providers/webhook/" in parts.path
            )
        except ValueError:
            valid_url = False
        if not valid_url:
            problems.append(f"{name}:callback_url_invalid")
    return {"ready": not problems, "reasons": tuple(problems)}
