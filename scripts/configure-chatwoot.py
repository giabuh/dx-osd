#!/usr/bin/env python3
"""
scripts/configure-chatwoot.py

Configures Chatwoot with default EduFlow Academy account, admin credentials,
and registers the webhook pointing to Frappe CRM. The webhook signing secret is
generated once (kept on re-runs) and copied into the CRM site config, which has
no built-in fallback secret.
"""

import subprocess
import sys

RUBY_SCRIPT = """
account = Account.first || Account.create!(name: 'EduFlow Academy')
user = User.find_by(email: 'admin@eduflow.vn') || User.find_by(email: 'admin@dx-osd.local')
if !user
  user = User.new(name: 'Administrator', email: 'admin@eduflow.vn', password: 'admin123', password_confirmation: 'admin123')
  user.skip_confirmation! if user.respond_to?(:skip_confirmation!)
  user.save!(validate: false)
end
account_user = AccountUser.find_or_create_by!(account: account, user: user)
account_user.update!(role: :administrator)

# Ensure webhook is configured
# Service names on the unified stack's shared_net; host.docker.internal cannot reach ports bound to 127.0.0.1.
target_url = 'http://crm-frappe:8000/api/method/mmm_custom.api.chatwoot_sync'
Webhook.where(account: account).where("url LIKE ?", '%/mmm_custom.api.chatwoot_sync').where.not(url: target_url).destroy_all
webhook = Webhook.find_or_initialize_by(account: account, url: target_url)
webhook.subscriptions = ['conversation_created', 'message_created']  # message_created feeds the optional [I] AI agents
webhook.webhook_type = :account_type
webhook.secret = SecureRandom.hex(32) if webhook.secret.blank?
webhook.save!

# Also configure Inbox for EduFlow Academy if not present
inbox = account.inboxes.find_by(name: 'EduFlow Academy Facebook')
if !inbox
  channel = Channel::Api.create!(account: account)
  inbox = Inbox.create!(account: account, channel: channel, name: 'EduFlow Academy Facebook')
  InboxMember.find_or_create_by!(inbox: inbox, user: user)
end

# Generate / retrieve API access token for Administrator
token = user.access_token&.token
if token.blank?
  access_token = user.create_access_token
  token = access_token.token
end

puts "SUCCESS"
puts "ACCOUNT_ID: #{account.id}"
puts "ACCOUNT_NAME: #{account.name}"
puts "ADMIN_EMAIL: #{user.email}"
masked_token = (token.present? && token.length > 8) ? "#{token[0..4]}...#{token[-4..-1]}" : "***"
puts "ADMIN_TOKEN: #{masked_token}"
puts "WEBHOOK_ID: #{webhook.id}"
puts "WEBHOOK_URL: #{webhook.url}"
puts "WEBHOOK_SECRET_VALUE=#{webhook.secret}"
puts "ADMIN_TOKEN_VALUE=#{token}"
puts "WEBHOOK_SUBSCRIPTIONS: #{webhook.subscriptions}"
puts "INBOX_ID: #{inbox.id}"
puts "INBOX_NAME: #{inbox.name}"
"""

def main():
    print("Configuring Chatwoot Account, Admin, and Webhook...")
    proc = subprocess.run(
        ["docker", "exec", "-i", "chatwoot-rails-1", "bundle", "exec", "rails", "runner", "-"],
        input=RUBY_SCRIPT.encode("utf-8"),
        capture_output=True,
    )
    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")
    if proc.returncode != 0:
        print("STDERR:\n", stderr)
        sys.exit(proc.returncode)
    values = {k: v for k, _, v in (line.partition("=") for line in stdout.splitlines()) if k in ("WEBHOOK_SECRET_VALUE", "ADMIN_TOKEN_VALUE")}
    print("\n".join(line for line in stdout.splitlines() if "_VALUE=" not in line))  # never print secrets

    # The CRM endpoint rejects every webhook until it knows the same secret, and needs an API token and a
    # URL reachable from inside the CRM container to write crm_lead_id back (and for the optional AI agents).
    site_config = {
        "chatwoot_webhook_secret": values["WEBHOOK_SECRET_VALUE"],
        "chatwoot_api_token": values["ADMIN_TOKEN_VALUE"],
        "chatwoot_api_url": "http://chatwoot-rails:3000",
    }
    for key, value in site_config.items():
        subprocess.run(
            ["docker", "exec", "-w", "/home/frappe/frappe-bench", "crm-frappe-1",
             "bench", "--site", "crm.localhost", "set-config", key, value],
            check=True, capture_output=True,
        )
    print("CRM site config: chatwoot_webhook_secret, chatwoot_api_token, chatwoot_api_url set")

if __name__ == "__main__":
    main()
