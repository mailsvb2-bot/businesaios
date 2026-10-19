from dataclasses import replace

import pytest

from runtime.business_autonomy.messenger_cutover_admission import (
    CHANNELS, ChannelTransferEvidence, check_cutover_admission,
)


def valid():
    return tuple(ChannelTransferEvidence(
        provider_key=name, account_identity=f"existing-{name}",
        legacy_worker_stopped=True, legacy_polling_stopped=True,
        new_credential_in_vault=True, new_ingress_ready=True,
        callback_url=f"https://new.example.org/providers/webhook/tenant/business/{name}",
        ownership_confirmed=True,
    ) for name in CHANNELS)


def check(items):
    return check_cutover_admission(items, expected_callback_host="new.example.org")


def test_three_existing_bot_identities_can_be_admitted_after_donor_shutdown():
    assert check(valid()) == {"ready": True, "reasons": ()}


@pytest.mark.parametrize("field", [
    "legacy_worker_stopped", "legacy_polling_stopped",
    "new_credential_in_vault", "new_ingress_ready", "ownership_confirmed",
])
def test_unknown_or_false_operational_proof_denies_cutover(field):
    items = valid()
    blocked = (replace(items[0], **{field: False}), *items[1:])
    assert check(blocked)["ready"] is False
    assert any(field in reason for reason in check(blocked)["reasons"])


@pytest.mark.parametrize("url", [
    "http://new.example.org/providers/webhook/tenant/business/telegram_bot",
    "https://old.example.org/providers/webhook/tenant/business/telegram_bot",
    "https://new.example.org@attacker.org/providers/webhook/tenant/business/telegram_bot",
    "https://new.example.org:444/providers/webhook/tenant/business/telegram_bot",
    "https://new.example.org/providers/webhook/tenant/business/vk_messaging",
    "https://new.example.org/providers/webhook/tenant/business/telegram_bot#fragment",
])
def test_bad_callback_route_never_admitted(url):
    items = valid()
    assert not check((replace(items[0], callback_url=url), *items[1:]))["ready"]


def test_missing_duplicate_or_renamed_provider_denied():
    items = valid()
    assert not check(items[:2])["ready"]
    assert not check((items[0], items[0], items[2]))["ready"]
    assert not check((replace(items[0], provider_key="new_telegram_bot"), *items[1:]))["ready"]
    assert not check((replace(items[0], account_identity=items[1].account_identity), *items[1:]))["ready"]
