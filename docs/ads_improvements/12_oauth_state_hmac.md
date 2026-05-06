# 12. OAuth state hardening (HMAC + expiry)

State must be signed (HMAC) and include tenant_id + nonce + ts; reject replay/expired. Store nonce in token store for one-time use.
