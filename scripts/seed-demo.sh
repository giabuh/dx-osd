#!/usr/bin/env bash
# One command for a full demo CRM: catalog, staff, bot knowledge, level tests and the sample customers
# (52 Leads, 15 registrations, notes, tasks, level-test attempts, Facebook posts with comments).
# Idempotent: re-running creates nothing new and moves the sample dates to today.
#
#   scripts/seed-demo.sh            # catalog + staff + sample customers
#   scripts/seed-demo.sh --reset    # first DELETE all customer/test data (CRM and Chatwoot), then seed
#   TYPESAFE_API_KEY=<key> scripts/seed-demo.sh   # also turn on Jev (the bot's AI understanding)
#
# Jev needs a TypeSafe API key. Without one the bot still answers from its rules and keywords, but the
# Playground's "Use Jev", Jev answers to customers, AI intent/hotness and the AI follow-ups stay off. The key is
# stored in the site config (never in git); see docs/demo-seed.md.
#
# --reset is destructive (Leads, registrations, notes, tasks, conversations, posts, Chatwoot conversations and
# contacts) and meant for dev/demo stacks only. Users, consultants, the catalog and the bot setup stay.
set -euo pipefail

cd "$(dirname "$0")/.."

RESET=0
for arg in "$@"; do
  case "$arg" in
    --reset) RESET=1 ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 2 ;;
  esac
done

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
die()  { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

bench() {
  docker exec -w /home/frappe/frappe-bench crm-frappe-1 bench --site crm.localhost "$@"
}

docker ps --format '{{.Names}}' | grep -qx crm-frappe-1 || die "crm-frappe-1 is not running (docker compose up -d)"

if (( RESET )); then
  step "Reset: deleting all customer and test data in the CRM"
  bench execute mmm_custom.demo.customers.reset

  step "Reset: deleting all Chatwoot conversations and contacts (agents, teams, inboxes, bot, webhooks stay)"
  if docker ps --format '{{.Names}}' | grep -qx chatwoot-rails-1; then
    # the runner logs a lot of Sidekiq/ActiveJob noise: show only the result line, everything if it fails
    if ! out=$(docker exec chatwoot-rails-1 bundle exec rails runner '
      account = Account.first
      if account.nil?
        puts "no Chatwoot account yet: nothing to delete"
      else
        conversations = account.conversations.count
        contacts = account.contacts.count
        account.conversations.destroy_all
        account.contacts.destroy_all
        puts "deleted conversations=#{conversations} contacts=#{contacts}; left conversations=#{account.conversations.count} contacts=#{account.contacts.count}"
      end' 2>&1); then
      echo "$out" >&2; die "Chatwoot wipe failed"
    fi
    echo "$out" | grep -E '^(deleted|no Chatwoot)' || { echo "$out" >&2; die "Chatwoot wipe printed no result"; }
  else
    echo "    chatwoot-rails-1 is not running: skipped"
  fi
fi

step "Catalog, branches, courses, schedules, promotions, consultants, bot skills"
bench execute mmm_custom.demo.loader.load

step "Staff mirrored to Chatwoot, same demo logins in both apps"
bench execute mmm_custom.staff_sync.sync_now
python3 scripts/seed-demo-logins.py

step "Sample customers (Leads, registrations, notes, tasks, level tests, Facebook posts)"
bench execute mmm_custom.demo.customers.seed

step "Jev (AI understanding)"
if [[ -n "${TYPESAFE_API_KEY:-}" ]]; then
  bench set-config typesafe_api_key "$TYPESAFE_API_KEY" >/dev/null
  bench execute frappe.db.set_single_value --args '["Lead Engine Settings", "jev_live", 1]' >/dev/null
  echo "    typesafe_api_key set, Lead Engine Settings > Jev answers real customers: on"
fi
if docker exec crm-frappe-1 python3 -c "import json,sys; c=json.load(open('/home/frappe/frappe-bench/sites/crm.localhost/site_config.json')); sys.exit(0 if c.get('typesafe_api_key') else 1)"; then
  echo "    Jev: key present"
else
  printf '\033[1;33m    Jev is OFF: no typesafe_api_key in the site config.\033[0m\n'
  echo "    The bot answers from rules only. To turn Jev on, re-run with your key:"
  echo "        TYPESAFE_API_KEY=<key> scripts/seed-demo.sh"
  echo "    (details: docs/demo-seed.md)"
fi

step "Result"
bench execute mmm_custom.demo.customers.summary
