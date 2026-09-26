#!/usr/bin/env python3
"""
scripts/setup-facebook-channel.py

Configures Chatwoot with a live Facebook Page Channel (EduFlow Academy)
and creates the corresponding Facebook Inbox and Verify Token.
"""

import os
import sys
import subprocess

RUBY_SCRIPT = """
account = Account.first || Account.create!(name: 'EduFlow Academy')
user = User.find_by(email: 'admin@eduflow.vn') || User.find_by(email: 'admin@dx-osd.local')

page_id = ENV['FB_PAGE_ID'] || '1334466483083776'
page_token = ENV['FB_PAGE_ACCESS_TOKEN']
verify_token = ENV['FB_VERIFY_TOKEN'] || 'eduflow_verify_2026'

if page_token.blank?
  puts "ERROR: FB_PAGE_ACCESS_TOKEN is required."
  exit 1
end

# Set verify token in Chatwoot
cfg = InstallationConfig.find_or_initialize_by(name: 'FB_VERIFY_TOKEN')
cfg.value = verify_token
cfg.save!

# Check or create Facebook Page Channel
channel = Channel::FacebookPage.find_or_initialize_by(page_id: page_id, account_id: account.id)
channel.page_access_token = page_token
channel.user_access_token = page_token
channel.save!

# Create Inbox for this channel if not exists
inbox = account.inboxes.find_by(channel: channel)
if !inbox
  inbox = Inbox.create!(account: account, channel: channel, name: 'EduFlow Messenger')
  InboxMember.find_or_create_by!(inbox: inbox, user: user) if user
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

    if not token:
        print("Usage: python scripts/setup-facebook-channel.py <PAGE_ACCESS_TOKEN>")
        sys.exit(1)

    page_id = os.environ.get("FB_PAGE_ID", "1334466483083776")
    verify_token = os.environ.get("FB_VERIFY_TOKEN", "eduflow_verify_2026")

    proc = subprocess.run(
        [
            "docker", "exec", "-i",
            "-e", f"FB_PAGE_ACCESS_TOKEN={token}",
            "-e", f"FB_PAGE_ID={page_id}",
            "-e", f"FB_VERIFY_TOKEN={verify_token}",
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
