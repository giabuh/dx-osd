#!/usr/bin/env python3
"""
scripts/setup-facebook-channel.py

Configures Chatwoot with a live Facebook Page channel and its inbox.
Required: FB_PAGE_ID, page access token (argument or FB_PAGE_ACCESS_TOKEN).
Optional: FB_VERIFY_TOKEN (default: keep the one already in Chatwoot), FB_INBOX_NAME.
"""

import os
import sys
import subprocess

RUBY_SCRIPT = """
account = Account.first
page_id = ENV['FB_PAGE_ID']
page_token = ENV['FB_PAGE_ACCESS_TOKEN']

if account.nil? || page_id.blank? || page_token.blank?
  puts "ERROR: an existing Account, FB_PAGE_ID and FB_PAGE_ACCESS_TOKEN are required."
  exit 1
end

# Set verify token in Chatwoot; keep the existing one unless FB_VERIFY_TOKEN is given
cfg = InstallationConfig.find_or_initialize_by(name: 'FB_VERIFY_TOKEN')
cfg.value = ENV['FB_VERIFY_TOKEN'] if ENV['FB_VERIFY_TOKEN'].present?
if cfg.value.blank?
  puts "ERROR: no FB_VERIFY_TOKEN in Chatwoot yet; pass FB_VERIFY_TOKEN."
  exit 1
end
cfg.save!
verify_token = cfg.value

# Check or create Facebook Page Channel
channel = Channel::FacebookPage.find_or_initialize_by(page_id: page_id, account_id: account.id)
channel.page_access_token = page_token
channel.user_access_token = page_token
channel.save!

# Create Inbox for this channel if not exists
inbox = account.inboxes.find_by(channel: channel)
if !inbox
  inbox = Inbox.create!(account: account, channel: channel, name: ENV['FB_INBOX_NAME'].presence || "Facebook #{page_id}")
  account.administrators.each { |admin| InboxMember.find_or_create_by!(inbox: inbox, user: admin) }
end

puts "SUCCESS"
puts "FACEBOOK_CHANNEL_ID: #{channel.id}"
puts "PAGE_ID: #{channel.page_id}"
puts "INBOX_ID: #{inbox.id}"
puts "INBOX_NAME: #{inbox.name}"
puts "VERIFY_TOKEN: #{verify_token}"
"""

def main():
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN")
    if not token and len(sys.argv) > 1:
        token = sys.argv[1]

    page_id = os.environ.get("FB_PAGE_ID")
    if not token or not page_id:
        print("Usage: FB_PAGE_ID=<PAGE_ID> python scripts/setup-facebook-channel.py <PAGE_ACCESS_TOKEN>")
        sys.exit(1)

    proc = subprocess.run(
        [
            "docker", "exec", "-i",
            "-e", f"FB_PAGE_ACCESS_TOKEN={token}",
            "-e", f"FB_PAGE_ID={page_id}",
            *[arg for name in ("FB_VERIFY_TOKEN", "FB_INBOX_NAME") if name in os.environ
              for arg in ("-e", f"{name}={os.environ[name]}")],
            "chatwoot-rails-1",
            "bundle", "exec", "rails", "runner", "-"
        ],
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
