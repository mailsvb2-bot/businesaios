# Ads OAuth / Token Provisioning

This repository provides a canonical **Ads Connector Layer** with a token store (`SQLiteAdsTokenStore`).

## Connect flow (OAuth)

1) Call connector.connect(OAuthConnectRequest) to get an authorization URL.
2) User completes OAuth consent on the ad platform.
3) Your web callback handler exchanges `code` for `access_token` / `refresh_token`.
4) Store tokens:

```python
await ads_tokens.upsert(
  tenant_id=tenant_id,
  platform=platform,
  account_id=account_id,
  access_token=access_token,
  refresh_token=refresh_token,
  expires_at_iso=expires_at_iso,
)
```

After this, the account is considered **connected** and will be picked up by Autopilot:
`ads_tokens.list_connected_accounts(tenant_id)`.

## Telegram Ads

Some Telegram Ads setups use an API token rather than OAuth.
In that case, store the token as `access_token` via the same `upsert()` call.

## Security

- Never log tokens
- Prefer storing tokens encrypted at rest (KMS/Vault) in production
