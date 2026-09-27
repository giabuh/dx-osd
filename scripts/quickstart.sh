#!/usr/bin/env bash
# One-command setup for a fresh clone: secrets, build, start, wire Chatwoot <-> CRM, demo data.
# Safe to re-run: every step is idempotent and existing data volumes are kept.
#
#   ./scripts/quickstart.sh            # full setup (first run: ~20-40 min, mostly the Chatwoot build + CRM bench init)
#   ./scripts/quickstart.sh --verify   # also run the unit tests and the live Chatwoot -> CRM test
#   ./scripts/quickstart.sh --no-demo  # skip the demo dataset
#
# Optional: TYPESAFE_API_KEY=<key> ./scripts/quickstart.sh   turns on the [I] AI agents.
set -euo pipefail

cd "$(dirname "$0")/.."

VERIFY=0
DEMO=1
for arg in "$@"; do
  case "$arg" in
    --verify) VERIFY=1 ;;
    --no-demo) DEMO=0 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m    ok:\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

bench() {
  docker exec -w /home/frappe/frappe-bench crm-frappe-1 bench --site crm.localhost "$@"
}

http_code() { curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$1" || true; }

# wait_for <description> <timeout seconds> <command...>
wait_for() {
  local what=$1 timeout=$2; shift 2
  local start=$SECONDS
  until "$@" >/dev/null 2>&1; do
    (( SECONDS - start > timeout )) && die "$what not ready after ${timeout}s (see: docker compose logs)"
    printf '.'; sleep 10
  done
  echo; ok "$what ($(( SECONDS - start ))s)"
}

step "Checking requirements"
command -v docker >/dev/null || die "docker is not installed"
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is required (docker compose ...)"
docker info >/dev/null 2>&1 || die "cannot talk to the Docker daemon (is it running? is your user in the docker group?)"
for bin in python3 openssl curl; do command -v "$bin" >/dev/null || die "$bin is not installed"; done
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' || die "Python >= 3.10 is required"
ok "docker, compose v2, python3, openssl, curl"

step "Chatwoot secrets (chatwoot/.env)"
if [[ -f chatwoot/.env ]]; then
  ok "chatwoot/.env exists, keeping it"
else
  cp chatwoot/.env.example chatwoot/.env
  sed -i.bak \
    -e "s|^SECRET_KEY_BASE=.*|SECRET_KEY_BASE=$(openssl rand -hex 64)|" \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(openssl rand -hex 16)|" \
    -e "s|^REDIS_PASSWORD=.*|REDIS_PASSWORD=$(openssl rand -hex 16)|" \
    -e "s|^FRONTEND_URL=.*|FRONTEND_URL=http://127.0.0.1:3000|" \
    -e "s|^RAILS_ENV=.*|RAILS_ENV=production|" \
    chatwoot/.env && rm -f chatwoot/.env.bak
  ok "generated chatwoot/.env with random secrets (gitignored)"
fi

step "Building Chatwoot from chatwoot/ (first run: ~10-20 min)"
docker compose build chatwoot-rails
ok "image dx-osd/chatwoot:local"

step "Preparing the Chatwoot database"
docker compose up -d chatwoot-postgres chatwoot-redis
wait_for "PostgreSQL" 120 docker exec chatwoot-postgres-1 pg_isready -U postgres
docker compose run --rm chatwoot-rails bundle exec rails db:chatwoot_prepare
ok "database migrated"

step "Starting the whole stack"
docker compose up -d
chatwoot_up() { [[ $(http_code http://127.0.0.1:3000) =~ ^(200|302)$ ]]; }
wait_for "Chatwoot on :3000" 600 chatwoot_up

echo "    Frappe CRM: the first start runs 'bench init' + builds the CRM frontend (~10-20 min)."
echo "    Follow it in another terminal with: docker compose logs -f crm-frappe"
crm_up() { [[ $(http_code http://127.0.0.1:8000) == 200 ]] && bench list-apps 2>/dev/null | grep -q mmm_custom; }
wait_for "Frappe CRM on :8000 with mmm_custom" 2700 crm_up

step "Wiring Chatwoot to the CRM (account, inbox, webhook, agent bot)"
python3 scripts/configure-chatwoot.py
python3 scripts/setup-agent-bot.py

if [[ -n "${TYPESAFE_API_KEY:-}" ]]; then
  step "Enabling the [I] AI agents"
  bench set-config typesafe_api_key "$TYPESAFE_API_KEY" >/dev/null
  ok "typesafe_api_key set"
fi

if (( DEMO )); then
  step "Loading the demo dataset (branches, staff, courses, schedules, promotions, bot skills)"
  bench execute mmm_custom.demo.loader.load
  bench execute mmm_custom.staff_sync.sync_now
  ok "demo data loaded and staff mirrored to Chatwoot"
  step "Same demo logins in both apps"
  python3 scripts/seed-demo-logins.py
fi

if (( VERIFY )); then
  step "Unit tests"
  python3 -m unittest discover -s frappe-custom/mmm_custom/mmm_custom/tests
  step "Live Chatwoot -> CRM test"
  SECRET=$(docker exec crm-frappe-1 python3 -c "import json; print(json.load(open('/home/frappe/frappe-bench/sites/crm.localhost/site_config.json'))['chatwoot_webhook_secret'])")
  python3 scripts/test-chatwoot-crm-sync.py --secret "$SECRET"
fi

cat <<'EOF'

==================================================================
 DX-OSD is up.

   Frappe CRM   http://127.0.0.1:8000
   Chatwoot     http://127.0.0.1:3000

 Same login in both apps:
   admin        admin@eduflow.vn / admin123   (CRM also: Administrator / admin123)
   consultant   any consultant email / EduFlow@2026
                e.g. mai.hcm-bt@demo.saoviet.invalid (branch team lead)

 Stop:     docker compose stop       (keeps all data)
 Restart:  docker compose up -d
 Never run `docker compose down -v`: the volumes hold the data.
==================================================================
EOF
