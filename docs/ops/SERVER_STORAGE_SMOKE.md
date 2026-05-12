# BusinesAIOS server storage smoke

This ops gate is for the staging server path:

```text
/opt/businesaios
```

It exposes two different modes and they must not be confused:

1. Read-only readiness/control-plane status.
2. Explicit live smoke that opens configured durable stores and can initialize schemas.

## 1. Bootstrap on server

```bash
sudo mkdir -p /opt/businesaios
sudo chown -R businesaios:businesaios /opt/businesaios
cd /opt/businesaios

git clone https://github.com/mailsvb2-bot/businesaios.git .
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.lock.txt
```

## 2. Required env

Create `/opt/businesaios/.env` with real server values. Do not commit this file.

```dotenv
APP_ENV=prod
STORAGE_BACKEND=postgres
METRO_DB_ENGINE=postgres
POSTGRES_DSN=postgresql://USER:PASSWORD@HOST:5432/DBNAME
BUSINESAIOS_DATA_DIR=/opt/businesaios/data/runtime
```

## 3. Read-only status

This does not open DB connections and does not initialize schemas.

```bash
cd /opt/businesaios
. .venv/bin/activate
python -m scripts.ops.storage_status --env-file /opt/businesaios/.env --pretty
```

Expected healthy configuration shape:

```json
{
  "surface": "admin.control_plane.storage",
  "admin_visible": true,
  "status": "ready",
  "read_only": true,
  "side_effects": false,
  "live_smoke_checked": false
}
```

Important: `status=ready` here means configuration readiness only. It is not proof that a live Postgres connection worked.

## 4. Explicit live smoke

This opens canonical durable stores through `runtime.wiring.build_durable_stores()` and calls `ping()` per role.
It can create/initialize schemas. Run it only as an explicit ops gate.

```bash
cd /opt/businesaios
. .venv/bin/activate
python -m scripts.ops.storage_status --env-file /opt/businesaios/.env --base-dir /opt/businesaios/data/runtime --live --pretty
```

Expected successful shape:

```json
{
  "surface": "runtime.storage.live_smoke",
  "status": "passed",
  "ok": true,
  "side_effects": true,
  "live_smoke_checked": true,
  "role_status": {
    "event_store": true,
    "ledger": true,
    "snapshot_store": true,
    "decision_archive": true,
    "outbox": true,
    "payment_outbox": true
  }
}
```

Exit codes:

```text
0 = ready / live smoke passed
1 = read-only readiness blocked
2 = live smoke blocked or failed
3 = script/runtime error before status payload
```

## 5. systemd oneshot

Install unit:

```bash
sudo cp /opt/businesaios/deploy/systemd/businesaios-storage-smoke.service /etc/systemd/system/businesaios-storage-smoke.service
sudo systemctl daemon-reload
sudo systemctl start businesaios-storage-smoke.service
sudo systemctl status businesaios-storage-smoke.service --no-pager
journalctl -u businesaios-storage-smoke.service -n 100 --no-pager
```

This unit is intentionally oneshot. It should not be used as the main application service.

## 6. Safety notes

- The CLI redacts Postgres DSN values in JSON output.
- Read-only mode must be used for admin/control-plane status.
- Live mode is an ops gate and has side effects.
- A configured DSN is not the same as a verified live integration.
- Passing this smoke still does not prove the full canonical chain `decision -> execution -> verification -> evidence -> archive`.
