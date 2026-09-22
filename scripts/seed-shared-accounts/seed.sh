#!/usr/bin/env bash
# Seeds matching demo staff accounts (same email + same password) into both
# Chatwoot and Frappe CRM, since Chatwoot CE has no built-in way to accept a
# custom OAuth/SSO provider without patching its code. See accounts.json for
# the user list. Passwords are generated fresh each run and written only to
# the gitignored credentials.local.json — never committed.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACCOUNTS_FILE="$SCRIPT_DIR/accounts.json"
CREDENTIALS_FILE="$SCRIPT_DIR/credentials.local.json"

FRAPPE_ADMIN_PASSWORD="${FRAPPE_ADMIN_PASSWORD:?set FRAPPE_ADMIN_PASSWORD to the Administrator password}"

source "$SCRIPT_DIR/seed-frappe.sh"
source "$SCRIPT_DIR/seed-chatwoot.sh"

CHATWOOT_URL=$(jq -r '.chatwoot.url' "$ACCOUNTS_FILE")
CHATWOOT_CONTAINER=$(jq -r '.chatwoot.container' "$ACCOUNTS_FILE")
CHATWOOT_ACCOUNT_ID=$(jq -r '.chatwoot.account_id' "$ACCOUNTS_FILE")
FRAPPE_URL=$(jq -r '.frappe.url' "$ACCOUNTS_FILE")
FRAPPE_HOST=$(jq -r '.frappe.host_header' "$ACCOUNTS_FILE")

COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT
frappe_login "$FRAPPE_URL" "$FRAPPE_HOST" "$FRAPPE_ADMIN_PASSWORD" "$COOKIE_JAR"

echo "[]" > "$CREDENTIALS_FILE"

user_count=$(jq '.users | length' "$ACCOUNTS_FILE")
for i in $(seq 0 $((user_count - 1))); do
  name=$(jq -r ".users[$i].name" "$ACCOUNTS_FILE")
  email=$(jq -r ".users[$i].email" "$ACCOUNTS_FILE")
  chatwoot_role=$(jq -r ".users[$i].chatwoot_role" "$ACCOUNTS_FILE")
  frappe_roles_json=$(jq -c ".users[$i].frappe_roles | map({role: .})" "$ACCOUNTS_FILE")
  # Chatwoot requires upper+lower+digit+special; hex is lower+digit only,
  # so append fixed chars covering the other two classes.
  password="$(openssl rand -hex 12)Aa1!"

  frappe_upsert_user "$FRAPPE_URL" "$FRAPPE_HOST" "$COOKIE_JAR" "$email" "$name" "$password" "$frappe_roles_json"
  chatwoot_upsert_user "$CHATWOOT_CONTAINER" "$CHATWOOT_ACCOUNT_ID" "$email" "$name" "$password" "$chatwoot_role"

  jq --arg email "$email" --arg name "$name" --arg password "$password" \
    '. += [{"name": $name, "email": $email, "password": $password}]' \
    "$CREDENTIALS_FILE" > "$CREDENTIALS_FILE.tmp" && mv "$CREDENTIALS_FILE.tmp" "$CREDENTIALS_FILE"
done

echo
echo "Done. Shared credentials written to $CREDENTIALS_FILE (gitignored, not committed)."
echo "Log in with the same email + password at both:"
echo "  Chatwoot:  $CHATWOOT_URL"
echo "  Frappe CRM (Host: $FRAPPE_HOST): $FRAPPE_URL"
