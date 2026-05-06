#!/usr/bin/env bash
set -euo pipefail

# CI / operator guard.
# Stops unsafe prod deployments with clear, Russian hints.
#
# Validations (only when ENV=prod):
#  - PRODUCTION_STRICT_MODE must be enabled
#  - ALLOW_SELF_APPROVE must be disabled
#  - ADMIN_USER_IDS must include at least 2 Telegram IDs
#
# Inputs (priority order):
#  1) Current process environment (CI variables)
#  2) docker-compose*.yml (environment + env_file)
#  3) common env files (.env, prod.env, .env.prod, etc.)
#
# Usage:
#   ci/check_prod_strict.sh            # auto-discover and check
#   ci/check_prod_strict.sh prod.env   # additionally parses explicit env files

die() {
  echo -e "$1" >&2
  exit 2
}

norm_bool() {
  local v="${1:-}"; v="${v,,}"
  if [[ "$v" == "1" || "$v" == "true" || "$v" == "yes" || "$v" == "on" ]]; then
    echo "1"; return
  fi
  echo "0"
}

count_admins() {
  # NOTE: pass raw list via argv to keep shell quoting predictable.
  python - "${1:-}" <<'PY'
import sys
raw=sys.argv[1] if len(sys.argv)>1 else ""
parts=[p.strip() for p in raw.split(',') if p.strip()]
print(len(parts))
PY
}

declare -A VAL
declare -A SRC

set_var_if_empty() {
  local k="$1"; local v="$2"; local s="$3"
  if [[ -z "${VAL[$k]+x}" ]]; then
    VAL[$k]="$v"
    SRC[$k]="$s"
  fi
}

set_var_force() {
  local k="$1"; local v="$2"; local s="$3"
  VAL[$k]="$v"
  SRC[$k]="$s"
}

parse_env_file() {
  local f="$1"
  [[ -f "$f" ]] || return 0
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%%$'\r'}"
    [[ -z "$line" ]] && continue
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" =~ ^[[:space:]]*export[[:space:]]+ ]] && line="${line#export }"

    if [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      local k="${BASH_REMATCH[1]}"
      local v="${BASH_REMATCH[2]}"
      v="${v%\"}"; v="${v#\"}"
      v="${v%\'}"; v="${v#\'}"
      case "$k" in
        ENV|APP_ENV|PRODUCTION_STRICT_MODE|ALLOW_SELF_APPROVE|ADMIN_USER_IDS)
          set_var_if_empty "$k" "$v" "$f"
          ;;
      esac
    fi
  done < "$f"
}

parse_compose_file() {
  local f="$1"
  [[ -f "$f" ]] || return 0

  # 1) env_file references
  local envfiles
  envfiles=$(python - <<'PY'
import re,sys
path=sys.argv[1]
lines=open(path,'r',encoding='utf-8',errors='ignore').read().splitlines()
files=[]
in_envfile=False
indent=None
for raw in lines:
    if not raw.strip() or raw.lstrip().startswith('#'):
        continue
    if re.match(r'^\s*env_file\s*:\s*$', raw):
        in_envfile=True
        indent=len(raw)-len(raw.lstrip())
        continue
    if in_envfile:
        s=raw.strip()
        m=re.match(r'^-\s*(.+)$', s)
        if m:
            files.append(m.group(1).strip().strip('"\''))
            continue
        # stop when we leave the block
        cur_indent=len(raw)-len(raw.lstrip())
        if cur_indent<=indent and re.match(r'^\s*[A-Za-z_\-]+\s*:', raw):
            in_envfile=False
            continue
    m=re.match(r'^\s*env_file\s*:\s*(.+)$', raw.strip())
    if m:
        files.append(m.group(1).strip().strip('"\''))

print("\n".join(files))
PY
"$f")

  if [[ -n "$envfiles" ]]; then
    local base
    base="$(cd "$(dirname "$f")" && pwd)"
    while IFS= read -r ef; do
      [[ -z "$ef" ]] && continue
      local full="$base/$ef"
      if [[ -f "$full" ]]; then
        parse_env_file "$full"
      fi
    done <<< "$envfiles"
  fi

  # 2) environment entries
  python - <<'PY'
import re,sys
path=sys.argv[1]
out=[]
lines=open(path,'r',encoding='utf-8',errors='ignore').read().splitlines()
in_env=False
indent=None
for raw in lines:
    if not raw.strip() or raw.lstrip().startswith('#'):
        continue
    if re.match(r'^\s*environment\s*:\s*$', raw):
        in_env=True
        indent=len(raw)-len(raw.lstrip())
        continue
    if in_env:
        cur_indent=len(raw)-len(raw.lstrip())
        if cur_indent<=indent and re.match(r'^\s*[A-Za-z_\-]+\s*:', raw):
            in_env=False
            continue
        s=raw.strip()
        m=re.match(r'^-\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$', s)
        if m:
            out.append((m.group(1), m.group(2).strip().strip('"\'')))
            continue
        m=re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$', s)
        if m:
            out.append((m.group(1), m.group(2).strip().strip('"\'')))

for k,v in out:
    if k in {'ENV','APP_ENV','PRODUCTION_STRICT_MODE','ALLOW_SELF_APPROVE','ADMIN_USER_IDS'}:
        print(f"{k}={v}")
PY
"$f" | while IFS= read -r kv; do
  [[ -z "$kv" ]] && continue
  local k="${kv%%=*}"; local v="${kv#*=}"
  set_var_if_empty "$k" "$v" "$f"
done
}

discover_sources() {
  # Highest priority: current environment
  [[ -n "${ENV:-}" ]] && set_var_force "ENV" "$ENV" "CI_ENV"
  [[ -n "${APP_ENV:-}" ]] && set_var_force "APP_ENV" "$APP_ENV" "CI_ENV"
  [[ -n "${PRODUCTION_STRICT_MODE:-}" ]] && set_var_force "PRODUCTION_STRICT_MODE" "$PRODUCTION_STRICT_MODE" "CI_ENV"
  [[ -n "${ALLOW_SELF_APPROVE:-}" ]] && set_var_force "ALLOW_SELF_APPROVE" "$ALLOW_SELF_APPROVE" "CI_ENV"
  [[ -n "${ADMIN_USER_IDS:-}" ]] && set_var_force "ADMIN_USER_IDS" "$ADMIN_USER_IDS" "CI_ENV"

  # Common env files
  local env_candidates=(
    ".env" "prod.env" ".env.prod" ".env.production" "env/prod.env" "config/prod.env"
  )
  for f in "${env_candidates[@]}"; do
    parse_env_file "$f"
  done

  # Compose files
  local compose_candidates=("docker-compose.yml" "docker-compose.prod.yml" "compose.yml" "compose.prod.yml")
  for f in "${compose_candidates[@]}"; do
    parse_compose_file "$f"
  done
}

fail_with_hint() {
  local title="$1"; local hint="$2"
  die "${title}\n\n${hint}"
}

check_effective() {
  discover_sources

  local envv="${VAL[ENV]:-${VAL[APP_ENV]:-}}"
  envv="${envv,,}"
  [[ -z "$envv" ]] && exit 0
  [[ "$envv" != "prod" ]] && exit 0

  local strict="${VAL[PRODUCTION_STRICT_MODE]:-}"
  local allow_self="${VAL[ALLOW_SELF_APPROVE]:-}"
  local admins="${VAL[ADMIN_USER_IDS]:-}"

  if [[ "$(norm_bool "$strict")" != "1" ]]; then
    local src="${SRC[PRODUCTION_STRICT_MODE]:-${SRC[ENV]:-${SRC[APP_ENV]:-unknown}}}"
    fail_with_hint \
      "⛔ CI / GOVERNANCE GUARD: ENV=prod требует PRODUCTION_STRICT_MODE=1" \
      "Исправь в: ${src}\n\nВпиши:\n  PRODUCTION_STRICT_MODE=1"
  fi

  if [[ "$(norm_bool "$allow_self")" == "1" ]]; then
    local src="${SRC[ALLOW_SELF_APPROVE]:-unknown}"
    fail_with_hint \
      "⛔ CI / GOVERNANCE GUARD: В проде запрещён ALLOW_SELF_APPROVE=1" \
      "Исправь в: ${src}\n\nВ проде нужно 2 администратора.\nДобавь второго админа в ADMIN_USER_IDS, например:\n  ADMIN_USER_IDS=123456789,987654321\n\nALLOW_SELF_APPROVE=1 допускается только локально/на стенде."
  fi

  local cnt
  cnt=$(count_admins "$admins")
  if [[ "$cnt" -lt 2 ]]; then
    local src="${SRC[ADMIN_USER_IDS]:-unknown}"
    fail_with_hint \
      "⛔ CI / GOVERNANCE GUARD: В проде требуется минимум 2 администратора" \
      "У тебя предусмотрено 2 админа.\nДобавь второго администратора в: ${src}\n\nДля добавления админа впиши его Telegram ID через запятую:\n  ADMIN_USER_IDS=123456789,987654321\n\nЕсли ты временно один — НЕ для прода: ALLOW_SELF_APPROVE=1"
  fi
}

# Legacy: if explicit files were provided, parse them first (higher priority than auto-discovery).
if [[ "$#" -gt 0 ]]; then
  for f in "$@"; do
    [[ -f "$f" ]] || die "ERROR: file not found: $f"
    parse_env_file "$f"
  done
fi

check_effective
