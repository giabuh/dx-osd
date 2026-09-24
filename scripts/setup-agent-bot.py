#!/usr/bin/env python3
"""
scripts/setup-agent-bot.py

Creates the EduFlow Qualification Bot as a Chatwoot Agent Bot, links it
to the EduFlow Messenger inbox, and configures the Frappe CRM site with
the bot's API token and webhook secret.
"""

import subprocess
import sys

RUBY_SCRIPT = """
account = Account.first
raise "No account found — run scripts/configure-chatwoot.py first" unless account

# Find the Facebook Messenger inbox
inbox = account.inboxes.find_by(channel_type: 'Channel::FacebookPage')
inbox ||= account.inboxes.first
raise "No inbox found" unless inbox

# Create or find the Agent Bot
bot_name = 'EduFlow Qualification Bot'
bot = AgentBot.find_or_initialize_by(name: bot_name, account: account)
bot.description = 'Collects course interest and branch preference via Quick Reply buttons'
bot.outgoing_url = 'http://host.docker.internal:8000/api/method/mmm_custom.bot_api.agent_bot_webhook'

# Generate a webhook secret for HMAC validation
require 'securerandom'
bot.secret ||= SecureRandom.hex(32)
bot.save!

# Link bot to inbox
abi = AgentBotInbox.find_or_initialize_by(inbox: inbox, agent_bot: bot)
abi.status = :active
abi.save!

# Get or create access token for the bot
token = bot.access_token&.token
if token.blank?
  access_token = bot.create_access_token
  token = access_token.token
end

puts "SUCCESS"
puts "BOT_ID: #{bot.id}"
puts "BOT_NAME: #{bot.name}"
puts "BOT_SECRET: #{bot.secret}"
puts "BOT_TOKEN: #{token}"
puts "INBOX_ID: #{inbox.id}"
puts "INBOX_NAME: #{inbox.name}"
puts "OUTGOING_URL: #{bot.outgoing_url}"
"""


def run_ruby(script: str) -> str:
    proc = subprocess.run(
        ["docker", "exec", "-i", "chatwoot-rails-1",
         "bundle", "exec", "rails", "runner", "-"],
        input=script.encode("utf-8"),
        capture_output=True,
    )
    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")
    if proc.returncode != 0:
        print("STDERR:", stderr)
        sys.exit(proc.returncode)
    return stdout


def configure_frappe(bot_secret: str, bot_token: str):
    """Set Frappe site config keys for the bot."""
    cmds = [
        f'bench --site crm.localhost set-config chatwoot_bot_webhook_secret "{bot_secret}"',
        f'bench --site crm.localhost set-config chatwoot_bot_api_token "{bot_token}"',
        'bench --site crm.localhost set-config chatwoot_bot_account_id 1',
        'bench --site crm.localhost set-config chatwoot_base_url "http://host.docker.internal:3000"',
    ]
    for cmd in cmds:
        subprocess.run(
            ["docker", "compose", "-f", "crm/docker/docker-compose.yml",
             "-f", "crm/docker/docker-compose.override.yml",
             "exec", "-T", "frappe", "bash", "-c", cmd],
            check=True,
        )


def run_setup():
    """Run mmm_custom.setup.setup to create custom fields."""
    subprocess.run(
        ["docker", "compose", "-f", "crm/docker/docker-compose.yml",
         "-f", "crm/docker/docker-compose.override.yml",
         "exec", "-T", "frappe",
         "bench", "--site", "crm.localhost", "execute",
         "mmm_custom.setup.setup"],
        check=True,
    )


def main():
    print("=== Step 1: Creating Agent Bot in Chatwoot ===")
    output = run_ruby(RUBY_SCRIPT)

    # Parse output and display non-sensitive lines
    lines = output.strip().split("\n")
    data = {}
    for line in lines:
        if ": " in line:
            key, val = line.split(": ", 1)
            data[key.strip()] = val.strip()
        if not any(k in line for k in ("BOT_SECRET", "BOT_TOKEN")):
            print(line)

    bot_secret = data.get("BOT_SECRET", "")
    bot_token = data.get("BOT_TOKEN", "")

    if not bot_secret or not bot_token:
        print("ERROR: Could not extract bot credentials")
        sys.exit(1)

    print("\n=== Step 2: Configuring Frappe CRM site config ===")
    configure_frappe(bot_secret, bot_token)

    print("\n=== Step 3: Running mmm_custom setup (custom fields) ===")
    run_setup()

    masked_token = f"{bot_token[:5]}...{bot_token[-4:]}" if len(bot_token) > 8 else "***"
    masked_secret = f"{bot_secret[:5]}...{bot_secret[-4:]}" if len(bot_secret) > 8 else "***"

    print("\n" + "=" * 60)
    print("Agent Bot setup complete!")
    print(f"  Bot Token: {masked_token}")
    print(f"  Bot Secret: {masked_secret}")
    print(f"  Inbox: {data.get('INBOX_NAME', 'N/A')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
