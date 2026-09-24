#!/usr/bin/env python3
"""
scripts/configure-chatwoot.py

Configures Chatwoot with default EduFlow Academy account, admin credentials,
and registers the webhook pointing to Frappe CRM.
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
target_url = 'http://host.docker.internal:8000/api/method/mmm_custom.api.chatwoot_sync'
webhook = Webhook.find_or_initialize_by(account: account, url: target_url)
webhook.subscriptions = ['conversation_created']
webhook.webhook_type = :account_type
webhook.secret = 'dx_osd_shared_webhook_secret_2026'
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
puts "ADMIN_TOKEN: #{token}"
puts "WEBHOOK_ID: #{webhook.id}"
puts "WEBHOOK_URL: #{webhook.url}"
puts "WEBHOOK_SECRET: #{webhook.secret}"
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
    print(stdout)
    if proc.returncode != 0:
        print("STDERR:\n", stderr)
        sys.exit(proc.returncode)

if __name__ == "__main__":
    main()
