#!/usr/bin/env bash
# Upserts one Frappe User with a given password. Sourced by seed.sh.
set -euo pipefail

frappe_login() {
  local url="$1" host="$2" admin_password="$3" cookie_jar="$4"
  curl -sf -c "$cookie_jar" -X POST "$url/api/method/login" \
    -H "Host: $host" -H "Content-Type: application/json" \
    -d "{\"usr\":\"Administrator\",\"pwd\":\"$admin_password\"}" > /dev/null
}

frappe_upsert_user() {
  local url="$1" host="$2" cookie_jar="$3"
  local email="$4" name="$5" password="$6" roles_json="$7"
  local status
  status=$(curl -s -b "$cookie_jar" -H "Host: $host" \
    -o /dev/null -w "%{http_code}" "$url/api/resource/User/$email")

  if [ "$status" = "200" ]; then
    curl -sf -b "$cookie_jar" -X PUT "$url/api/resource/User/$email" \
      -H "Host: $host" -H "Content-Type: application/json" \
      -d "{\"new_password\":\"$password\"}" > /dev/null
    echo "frappe: updated password for $email"
  else
    curl -sf -b "$cookie_jar" -X POST "$url/api/resource/User" \
      -H "Host: $host" -H "Content-Type: application/json" \
      -d "{\"email\":\"$email\",\"first_name\":\"$name\",\"send_welcome_email\":0,\"new_password\":\"$password\",\"enabled\":1,\"roles\":$roles_json}" > /dev/null
    echo "frappe: created $email"
  fi
}
