#!/usr/bin/env bash
# Upserts one Chatwoot agent with a given password via `rails runner`,
# since Chatwoot CE's agent-invite API only sets a password through an
# email confirmation link, and this environment has no mailer configured.
set -euo pipefail

chatwoot_upsert_user() {
  local container="$1" account_id="$2"
  local email="$3" name="$4" password="$5" role="$6"

  docker exec -i \
    -e SEED_EMAIL="$email" \
    -e SEED_NAME="$name" \
    -e SEED_PASSWORD="$password" \
    -e SEED_ROLE="$role" \
    -e SEED_ACCOUNT_ID="$account_id" \
    "$container" bundle exec rails runner - <<'RUBY'
email = ENV.fetch('SEED_EMAIL')
name = ENV.fetch('SEED_NAME')
password = ENV.fetch('SEED_PASSWORD')
role = ENV.fetch('SEED_ROLE')
account_id = ENV.fetch('SEED_ACCOUNT_ID').to_i

user = User.find_or_initialize_by(email: email)
was_new = user.new_record?
user.name = name
user.password = password
user.password_confirmation = password
user.skip_confirmation! if user.respond_to?(:skip_confirmation!)
user.save!

account = Account.find(account_id)
account_user = AccountUser.find_or_initialize_by(account_id: account.id, user_id: user.id)
account_user.role = role
account_user.save!

puts "chatwoot: #{was_new ? 'created' : 'updated'} #{email} (role=#{role}, account=#{account.name})"
RUBY
}
