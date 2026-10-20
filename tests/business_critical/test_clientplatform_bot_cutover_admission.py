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
    "https://new.example.org/providers/webhook/tenant/business/telegram_bot?token=spoofed",
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


def test_telegram_only_staged_cutover_is_admitted_without_vk_or_max():
    telegram = valid()[0]
    assert check_cutover_admission(
        (telegram,), expected_callback_host="new.example.org",
        selected_providers=("telegram_bot",),
    ) == {"ready": True, "reasons": ()}


@pytest.mark.parametrize("field", [
    "legacy_worker_stopped", "legacy_polling_stopped",
    "new_credential_in_vault", "new_ingress_ready", "ownership_confirmed",
])
def test_telegram_only_still_requires_every_operational_proof(field):
    telegram = replace(valid()[0], **{field: False})
    result = check_cutover_admission(
        (telegram,), expected_callback_host="new.example.org",
        selected_providers=("telegram_bot",),
    )
    assert result["ready"] is False
    assert any(field in reason for reason in result["reasons"])


def test_selected_provider_identity_must_match_exactly():
    telegram = valid()[0]
    assert not check_cutover_admission(
        (telegram,), expected_callback_host="new.example.org",
        selected_providers=("vk_messaging",),
    )["ready"]
    for selection in ((), ("telegram_bot", "telegram_bot"), ("unknown",)):
        assert not check_cutover_admission(
            (telegram,), expected_callback_host="new.example.org",
            selected_providers=selection,
        )["ready"]


def test_telegram_long_polling_cutover_needs_no_webhook_but_real_proof():
    telegram = replace(valid()[0], transport_mode="long_polling", callback_url="")
    assert check_cutover_admission(
        (telegram,), expected_callback_host="new.example.org",
        selected_providers=("telegram_bot",),
    ) == {"ready": True, "reasons": ()}


@pytest.mark.parametrize("field", [
    "legacy_worker_stopped", "legacy_polling_stopped",
    "new_credential_in_vault", "new_ingress_ready", "ownership_confirmed",
])
def test_telegram_polling_missing_proof_fails_closed(field):
    telegram = replace(valid()[0], transport_mode="long_polling", callback_url="", **{field: False})
    result = check_cutover_admission(
        (telegram,), expected_callback_host="new.example.org",
        selected_providers=("telegram_bot",),
    )
    assert result["ready"] is False
    assert any(field in reason for reason in result["reasons"])


def test_polling_must_not_claim_webhook_and_other_channels_cannot_poll():
    telegram = replace(valid()[0], transport_mode="long_polling")
    assert not check_cutover_admission(
        (telegram,), expected_callback_host="new.example.org",
        selected_providers=("telegram_bot",),
    )["ready"]
    vk = replace(valid()[1], transport_mode="long_polling", callback_url="")
    assert not check_cutover_admission(
        (vk,), expected_callback_host="new.example.org",
        selected_providers=("vk_messaging",),
    )["ready"]
    unknown = replace(valid()[0], transport_mode="unknown", callback_url="")
    assert not check_cutover_admission(
        (unknown,), expected_callback_host="new.example.org",
        selected_providers=("telegram_bot",),
    )["ready"]


@pytest.mark.parametrize("bad_host", [
    "", "NEW.example.org", "new.example.org:443", "new.example.org/path",
    "new.example.org@attacker.org", "new.example.org?x=1", "[",
])
def test_invalid_expected_callback_authority_fails_closed(bad_host):
    assert check_cutover_admission(valid(), expected_callback_host=bad_host)["ready"] is False


@pytest.mark.parametrize("bad_identity", [None, 123, "", "  "])
def test_invalid_provider_identity_never_crashes_or_admits(bad_identity):
    items = valid()
    result = check_cutover_admission(
        (replace(items[0], account_identity=bad_identity), *items[1:]),
        expected_callback_host="new.example.org",
    )
    assert result["ready"] is False


@pytest.mark.parametrize("selection", [None, [], ["telegram_bot"], ("telegram_bot", None), (42,)])
def test_malformed_provider_selection_fails_closed(selection):
    assert check_cutover_admission(
        (valid()[0],), expected_callback_host="new.example.org",
        selected_providers=selection,
    )["ready"] is False


@pytest.mark.parametrize("evidence", [None, [], (None,), ({"provider_key": "telegram_bot"},)])
def test_malformed_evidence_fails_closed(evidence):
    assert check_cutover_admission(
        evidence, expected_callback_host="new.example.org",
        selected_providers=("telegram_bot",),
    )["ready"] is False


@pytest.mark.parametrize("field,bad_value", [
    ("account_identity", []), ("account_identity", {}),
    ("provider_key", []), ("provider_key", {}),
    ("callback_url", None), ("callback_url", []),
])
def test_unhashable_or_malformed_cutover_evidence_fails_closed(field, bad_value):
    items = valid()
    result = check((replace(items[0], **{field: bad_value}), *items[1:]))
    assert result["ready"] is False


def test_polling_malformed_callback_fails_closed():
    telegram = replace(valid()[0], transport_mode="long_polling", callback_url=None)
    result = check_cutover_admission(
        (telegram,), expected_callback_host="new.example.org",
        selected_providers=("telegram_bot",),
    )
    assert result["ready"] is False
