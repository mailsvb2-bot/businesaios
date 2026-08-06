#!/usr/bin/env bash
set -Eeuo pipefail

APP=/opt/businesaios
ENV_FILE=/etc/businesaios/api.env
SHA=8223e5c4903cce407972ca688f262a83ff8ba513
STAMP=$(date +%Y%m%d_%H%M%S)
BACKUP=/root/businesaios-backups/$STAMP
STAGE=/tmp/businesaios-release-$STAMP
VENV_ROOT=/opt/businesaios-venvs
NEW_VENV=$VENV_ROOT/$SHA
OLD_HEAD=""
OLD_VENV_KIND=none
OLD_VENV_VALUE=""
ACTIVATED=0

UNITS=(
  businesaios-api.service
  businesaios-worker.service
  businesaios-connector-telegram.service
  businesaios-telegram.service
  businesaios-evolution.service
)

log() { printf '\n=== %s ===\n' "$*"; }

restore_previous() {
  local rc=$?
  trap - ERR
  set +e

  if [[ "$ACTIVATED" == "1" ]]; then
    echo "РАЗВЁРТЫВАНИЕ НЕ УДАЛОСЬ. ВОССТАНАВЛИВАЮ ПРЕДЫДУЩУЮ ВЕРСИЮ..."
    systemctl stop "${UNITS[@]}" >/dev/null 2>&1 || true

    if [[ -n "$OLD_HEAD" ]]; then
      git -C "$APP" reset --hard "$OLD_HEAD" >/dev/null 2>&1 || true
    fi

    rm -rf "$APP/.venv"
    if [[ "$OLD_VENV_KIND" == "symlink" && -n "$OLD_VENV_VALUE" ]]; then
      ln -s "$OLD_VENV_VALUE" "$APP/.venv"
    elif [[ "$OLD_VENV_KIND" == "directory" && -d "$OLD_VENV_VALUE" ]]; then
      mv "$OLD_VENV_VALUE" "$APP/.venv"
    fi

    rm -f /etc/systemd/system/businesaios-{api,worker,connector-telegram,telegram,evolution}.service
    if compgen -G "$BACKUP/systemd/*" >/dev/null; then
      cp -a "$BACKUP/systemd/"* /etc/systemd/system/
    fi
    if [[ -f "$BACKUP/api.env" ]]; then
      install -m 0640 -o root -g businesaios "$BACKUP/api.env" "$ENV_FILE"
    fi

    systemctl daemon-reload
    systemctl restart businesaios-api.service >/dev/null 2>&1 || true
    echo "Предыдущий API восстановлен. База данных автоматически не откатывалась."
  else
    echo "Сервер не переключался: действующая версия не изменена."
  fi

  echo "Код ошибки: $rc"
  echo "Резервная копия: $BACKUP"
  exit "$rc"
}
trap restore_previous ERR

[[ $(id -u) -eq 0 ]] || { echo "Запустите от root"; exit 1; }
[[ -d "$APP/.git" ]] || { echo "Нет Git-репозитория $APP"; exit 1; }
[[ -f "$ENV_FILE" ]] || { echo "Нет рабочего файла $ENV_FILE"; exit 1; }

mkdir -p "$BACKUP/systemd" "$VENV_ROOT" "$STAGE"
OLD_HEAD=$(git -C "$APP" rev-parse HEAD)
printf '%s\n' "$OLD_HEAD" > "$BACKUP/old-head.txt"
cp -a "$ENV_FILE" "$BACKUP/api.env"

for unit in "${UNITS[@]}"; do
  [[ ! -f "/etc/systemd/system/$unit" ]] || cp -a "/etc/systemd/system/$unit" "$BACKUP/systemd/"
done

git -C "$APP" status --short --branch | tee "$BACKUP/git-status.txt"
git -C "$APP" diff > "$BACKUP/working.diff" || true

log "1. Зависимости"
apt-get update
apt-get install -y --no-install-recommends ca-certificates git python3 python3-venv python3-pip postgresql-client curl

getent group businesaios >/dev/null || groupadd --system businesaios
id businesaios >/dev/null 2>&1 || useradd --system --gid businesaios --home-dir /var/lib/businesaios --shell /usr/sbin/nologin businesaios

log "2. Проверка GitHub commit"
git -C "$APP" remote set-url origin https://github.com/mailsvb2-bot/businesaios.git
git -C "$APP" fetch --prune origin main
REMOTE=$(git -C "$APP" rev-parse origin/main)
[[ "$REMOTE" == "$SHA" ]] || {
  echo "main изменился: ожидался $SHA, получен $REMOTE"
  exit 1
}

git -C "$APP" archive "$SHA" | tar -x -C "$STAGE"

log "3. Подготовка production env без раскрытия секретов"
PID=$(systemctl show businesaios-api.service -p MainPID --value 2>/dev/null || echo 0)
[[ "$PID" =~ ^[0-9]+$ ]] || PID=0
PROC_ENV=""
if [[ "$PID" -gt 1 && -r "/proc/$PID/environ" ]]; then
  PROC_ENV="/proc/$PID/environ"
fi

python3 - "$ENV_FILE" "$PROC_ENV" "$BACKUP/api.env.candidate" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

source = Path(sys.argv[1])
proc_path = sys.argv[2]
target = Path(sys.argv[3])

recoverable = {
    "APP_ENV", "ENV", "TENANT_ID", "DATABASE_URL", "POSTGRES_DSN",
    "STORAGE_BACKEND", "STORAGE_DB_ENGINE", "METRO_DB_ENGINE",
    "BUSINESAIOS_ENABLE_POSTGRES_EVENT_STORE", "CONTROL_PLANE_API_KEY",
    "API_CONTROL_PLANE_API_KEY_PEPPER", "BUSINESAIOS_API_KEY_STORE_BACKEND",
    "BUSINESAIOS_API_KEY_STORE_PATH", "API_DOCS_ENABLED", "BAIOS_DATA_DIR",
    "BUSINESAIOS_DATA_DIR", "TELEGRAM_BOT_TOKEN", "TELEGRAM_USE_WEBHOOK",
    "TELEGRAM_WEBHOOK_ENABLED", "TELEGRAM_WEBHOOK_SECRET",
    "TELEGRAM_WEBHOOK_URL", "SECRET_VAULT_BACKEND", "KEY_PROVIDER_BACKEND",
    "BUSINESAIOS_SECRET_VAULT_BACKEND", "BUSINESAIOS_KEY_PROVIDER_BACKEND",
}

overrides = {
    "API_HOST": "0.0.0.0",
    "API_PORT": "8000",
    "HEALTH_HOST": "127.0.0.1",
    "WORKER_HEALTH_PORT": "8087",
    "EVOLUTION_HEALTH_PORT": "8087",
    "EVOLUTION_ENABLED": "1",
    "STORAGE_BACKEND": "postgres",
    "STORAGE_DB_ENGINE": "postgres",
    "BUSINESAIOS_ENABLE_POSTGRES_EVENT_STORE": "1",
}


def parse_lines(lines: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in lines:
        line = raw.strip()
        if line.startswith("export "):
            line = line[7:].lstrip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        result[key] = value
    return result


def quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'

original_lines = source.read_text(encoding="utf-8").splitlines()
values = parse_lines(original_lines)

if proc_path:
    raw = Path(proc_path).read_bytes().split(b"\0")
    process_values = {}
    for item in raw:
        if b"=" not in item:
            continue
        key, value = item.split(b"=", 1)
        process_values[key.decode("utf-8", "replace")] = value.decode("utf-8", "replace")
    for key in recoverable:
        if not values.get(key) and process_values.get(key):
            values[key] = process_values[key]

values.update(overrides)
managed = recoverable | set(overrides) | {"APP_PROFILE", "RUN_MODE"}
output: list[str] = []
for raw in original_lines:
    candidate = raw.strip()
    if candidate.startswith("export "):
        candidate = candidate[7:].lstrip()
    key = candidate.split("=", 1)[0].strip() if "=" in candidate else ""
    if key in managed:
        continue
    output.append(raw)

output.extend(["", "# Canonical multichannel runtime"])
for key in sorted(values):
    if key in managed and values[key] != "":
        output.append(f"{key}={quote(values[key])}")

target.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")

runtime_env = (values.get("APP_ENV") or values.get("ENV") or "").strip().lower()
dsn = (values.get("POSTGRES_DSN") or values.get("DATABASE_URL") or "").strip()
if runtime_env == "prod" and not dsn:
    print("ENV_ERROR=PROD_REQUIRES_POSTGRES_DSN")
    raise SystemExit(20)
if not dsn:
    print("ENV_ERROR=DATABASE_URL_OR_POSTGRES_DSN_MISSING")
    raise SystemExit(21)

print("ENV_SOURCE=/etc/businesaios/api.env")
print("PROCESS_ENV_RECOVERY=" + ("yes" if proc_path else "no"))
print("POSTGRES_DSN_PRESENT=yes")
print("TELEGRAM_CONNECTOR=" + ("1" if values.get("TELEGRAM_BOT_TOKEN") else "0"))
PY

DSN=$(python3 - "$BACKUP/api.env.candidate" <<'PY'
from pathlib import Path
import sys
values = {}
for raw in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    values[key.strip()] = value
print(values.get("POSTGRES_DSN") or values.get("DATABASE_URL") or "")
PY
)

TG=$(python3 - "$BACKUP/api.env.candidate" <<'PY'
from pathlib import Path
import sys
for raw in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if line.startswith("TELEGRAM_BOT_TOKEN="):
        value = line.split("=", 1)[1].strip().strip("\"'")
        print("1" if value else "0")
        break
else:
    print("0")
PY
)

pg_isready -d "$DSN"
pg_dump "$DSN" -Fc --no-owner --no-privileges -f "$BACKUP/postgres.dump"
test -s "$BACKUP/postgres.dump"

log "4. Новое изолированное Python-окружение"
rm -rf "$NEW_VENV"
python3 -m venv "$NEW_VENV"
"$NEW_VENV/bin/python" -m pip install --upgrade pip
LOCK=requirements.release.lock.txt
[[ -f "$STAGE/$LOCK" ]] || LOCK=requirements.lock.txt
"$NEW_VENV/bin/python" -m pip install -r "$STAGE/$LOCK"

(
  cd "$STAGE"
  "$NEW_VENV/bin/python" -m pytest -q \
    tests/deployment/test_server_deployment_contract.py \
    tests/unit/deployment/test_multichannel_systemd_contract.py \
    tests/unit/application/business_autonomy/test_multichannel_platform_contract.py
)

log "5. Резервное копирование runtime data"
for directory in "$APP/data" "$APP/runtime/data" "$APP/runtime_state" /var/lib/businesaios/runtime; do
  if [[ -e "$directory" ]]; then
    name=$(echo "${directory#/}" | tr '/' '_')
    tar -C / -czf "$BACKUP/$name.tar.gz" "${directory#/}"
  fi
done

log "6. Переключение на проверенный release"
systemctl stop "${UNITS[@]}" >/dev/null 2>&1 || true
ACTIVATED=1

if [[ -L "$APP/.venv" ]]; then
  OLD_VENV_KIND=symlink
  OLD_VENV_VALUE=$(readlink "$APP/.venv")
  rm "$APP/.venv"
elif [[ -d "$APP/.venv" ]]; then
  OLD_VENV_KIND=directory
  OLD_VENV_VALUE="$APP/.venv.rollback-$STAMP"
  mv "$APP/.venv" "$OLD_VENV_VALUE"
fi

cd "$APP"
git checkout -f main
git reset --hard "$SHA"
git clean -fd -e data/ -e runtime/data/ -e runtime_state/ -e '.venv*'
ln -s "$NEW_VENV" "$APP/.venv"

install -d -m 0750 -o root -g businesaios /etc/businesaios /etc/businesaios/connectors
install -m 0640 -o root -g businesaios "$BACKUP/api.env.candidate" "$ENV_FILE"
printf '%s\n' 'WORKER_HEALTH_PORT=8087' 'EVOLUTION_HEALTH_PORT=8087' 'EVOLUTION_ENABLED=1' > /etc/businesaios/worker.env
printf '%s\n' 'TELEGRAM_HEALTH_PORT=8088' > /etc/businesaios/connectors/telegram.env
chown root:businesaios /etc/businesaios/worker.env /etc/businesaios/connectors/telegram.env
chmod 0640 /etc/businesaios/worker.env /etc/businesaios/connectors/telegram.env

install -d -m 0750 -o businesaios -g businesaios /var/lib/businesaios/runtime "$APP/data" "$APP/runtime/data" "$APP/runtime_state"
chown -R businesaios:businesaios /var/lib/businesaios "$APP/data" "$APP/runtime/data" "$APP/runtime_state"
chmod 0755 /opt "$APP" "$VENV_ROOT" "$NEW_VENV"

cat > "$BACKUP/run-with-env.py" <<'PY'
from __future__ import annotations
import os, pwd, sys
from pathlib import Path

env_file, user, *command = sys.argv[1:]
env = dict(os.environ)
for raw in Path(env_file).read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    env[key.strip()] = value
account = pwd.getpwnam(user)
os.initgroups(account.pw_name, account.pw_gid)
os.setgid(account.pw_gid)
os.setuid(account.pw_uid)
os.execvpe(command[0], command, env)
PY

python3 "$BACKUP/run-with-env.py" "$ENV_FILE" businesaios "$APP/.venv/bin/python" -m scripts.server.migrate_before_start

APP_DIR="$APP" PYTHON_BIN="$APP/.venv/bin/python" ENABLE_TELEGRAM_CONNECTOR="$TG" START_SERVICES=0 bash deploy/systemd/install.sh

log "7. Последовательный запуск и health checks"
systemctl start businesaios-api.service
for attempt in $(seq 1 90); do
  if systemctl is-active --quiet businesaios-api.service && curl -fsS --max-time 3 http://127.0.0.1:8000/health >/dev/null; then
    break
  fi
  if [[ "$attempt" == "90" ]]; then
    journalctl -u businesaios-api.service -n 250 --no-pager
    false
  fi
  sleep 2
done
curl -fsS http://127.0.0.1:8000/readyz

systemctl start businesaios-worker.service
for attempt in $(seq 1 90); do
  if systemctl is-active --quiet businesaios-worker.service && curl -fsS --max-time 3 http://127.0.0.1:8087/health >/dev/null; then
    break
  fi
  if [[ "$attempt" == "90" ]]; then
    journalctl -u businesaios-worker.service -n 250 --no-pager
    false
  fi
  sleep 2
done

if [[ "$TG" == "1" ]]; then
  systemctl start businesaios-connector-telegram.service
  systemctl is-active --quiet businesaios-connector-telegram.service
fi

ACTIVATED=0
trap - ERR
rm -rf "$STAGE"

log "ГОТОВО"
echo "HEAD=$(git -C "$APP" rev-parse HEAD)"
echo "BACKUP=$BACKUP"
echo "API=active http://127.0.0.1:8000/health"
echo "WORKER=active http://127.0.0.1:8087/health"
echo "TELEGRAM_CONNECTOR=$TG"
echo "OLD_VENV=$OLD_VENV_VALUE"
