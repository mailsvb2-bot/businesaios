# Runtime host contract

This document records the production host contract for the BusinesAIOS API process.

## Required runtime path

The public API process must run through the server profile runner:

```bash
/opt/businesaios/.venv/bin/python -m scripts.server.run_profile
```

The API profile binds to `127.0.0.1:8000` by default. Nginx is the public TLS boundary and must proxy `api.businessaios.ru` and `status.businessaios.ru` to that local upstream.

## Required checks

Before declaring the host healthy, verify:

```bash
systemctl status businesaios-api.service --no-pager -l
systemctl status nginx --no-pager -l
nginx -t
curl -fsS http://127.0.0.1:8000/healthz
curl -fsS https://api.businessaios.ru/healthz
curl -fsS https://status.businessaios.ru/healthz
```

## Known failure mode

A stale nginx upstream such as `127.0.0.1:8090` causes external `502` while the local API is healthy on `127.0.0.1:8000`.

A broken systemd unit that references a missing environment file or an executable named `start` fails before Python is reached. The canonical unit must use the Python module entrypoint above.

## Noise scan handling

Common Exchange probe paths such as `/owa/`, `/ews/exchange.asmx`, `/autodiscover/autodiscover.xml`, `/Microsoft-Server-ActiveSync`, `/ecp/`, `/mapi/`, and `/rpc/` should be rejected at nginx before they reach FastAPI logs.
