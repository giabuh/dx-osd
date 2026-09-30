#!/usr/bin/env python3
"""
scripts/configure-chatwoot.py

Configures Chatwoot with default EduFlow Academy account, admin credentials,
and registers the webhook pointing to Frappe CRM. The webhook signing secret is
generated once (kept on re-runs) and copied into the CRM site config, which has
no built-in fallback secret.

Facebook App: when FB_APP_ID / FB_APP_SECRET (or FACEBOOK_APP_ID / FACEBOOK_APP_SECRET) and FB_VERIFY_TOKEN
are in the environment, .env or chatwoot/.env, they go into Chatwoot's app config and the CRM site config
(facebook_app_id, facebook_app_secret), so managers can connect pages from /crm/admin/channels.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FACEBOOK_KEYS = {"FB_APP_ID": ("FB_APP_ID", "FACEBOOK_APP_ID"),
                 "FB_APP_SECRET": ("FB_APP_SECRET", "FACEBOOK_APP_SECRET"),
                 "FB_VERIFY_TOKEN": ("FB_VERIFY_TOKEN",)}

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
# message_created feeds the optional [I] AI agents; conversation_updated tells them a staff member took a conversation
# and carries the assist banner's buttons; conversation_typing_on holds the bot back while a staff member types (D-112)
webhook.subscriptions = ['conversation_created', 'message_created', 'conversation_updated', 'conversation_typing_on']
webhook.webhook_type = :account_type
webhook.secret = SecureRandom.hex(32) if webhook.secret.blank?
webhook.save!

# Generate / retrieve API access token for Administrator
token = user.access_token&.token
if token.blank?
  access_token = user.create_access_token
  token = access_token.token
end

# Platform App: lets the CRM fetch each consultant's own Chatwoot token (staff_sync), so answers sent from
# a Lead's Messages tab go out under that consultant's name.
platform_app = PlatformApp.find_or_create_by!(name: 'EduFlow CRM')
platform_token = platform_app.access_token&.token || platform_app.create_access_token.token

# Facebook App (optional): lets Chatwoot verify Messenger webhooks and exchange tokens for connected pages.
%w[FB_APP_ID FB_APP_SECRET FB_VERIFY_TOKEN].each do |key|
  next if ENV[key].blank?
  cfg = InstallationConfig.find_or_initialize_by(name: key)
  cfg.value = ENV[key]
  cfg.save!
end
fb_ready = %w[FB_APP_ID FB_APP_SECRET FB_VERIFY_TOKEN].all? { |key| InstallationConfig.find_by(name: key)&.value.present? }

puts "SUCCESS"
puts "FACEBOOK_APP: #{fb_ready ? 'configured' : 'missing FB_APP_ID / FB_APP_SECRET / FB_VERIFY_TOKEN'}"
puts "ACCOUNT_ID: #{account.id}"
puts "ACCOUNT_NAME: #{account.name}"
puts "ADMIN_EMAIL: #{user.email}"
masked_token = (token.present? && token.length > 8) ? "#{token[0..4]}...#{token[-4..-1]}" : "***"
puts "ADMIN_TOKEN: #{masked_token}"
puts "WEBHOOK_ID: #{webhook.id}"
puts "WEBHOOK_URL: #{webhook.url}"
puts "WEBHOOK_SECRET_VALUE=#{webhook.secret}"
puts "ADMIN_TOKEN_VALUE=#{token}"
puts "PLATFORM_TOKEN_VALUE=#{platform_token}"
puts "WEBHOOK_SUBSCRIPTIONS: #{webhook.subscriptions}"
"""

def read_env_file(path):
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.strip().partition("=")
            if sep and not key.startswith("#"):
                values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def facebook_app():
    """FB_APP_ID / FB_APP_SECRET / FB_VERIFY_TOKEN from the environment, then .env, then chatwoot/.env."""
    sources = [dict(os.environ), read_env_file(ROOT / ".env"), read_env_file(ROOT / "chatwoot" / ".env")]
    found = {}
    for key, names in FACEBOOK_KEYS.items():
        found[key] = next((src[n] for src in sources for n in names if src.get(n)), "")
    return {k: v for k, v in found.items() if v}


def main():
    print("Configuring Chatwoot Account, Admin, and Webhook...")
    fb = facebook_app()
    env_args = [arg for key, value in fb.items() for arg in ("-e", f"{key}={value}")]
    proc = subprocess.run(
        ["docker", "exec", *env_args, "-i", "chatwoot-rails-1", "bundle", "exec", "rails", "runner", "-"],
        input=RUBY_SCRIPT.encode("utf-8"),
        capture_output=True,
    )
    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")
    if proc.returncode != 0:
        print("STDERR:\n", stderr)
        sys.exit(proc.returncode)
    values = {k: v for k, _, v in (line.partition("=") for line in stdout.splitlines()) if k in ("WEBHOOK_SECRET_VALUE", "ADMIN_TOKEN_VALUE", "PLATFORM_TOKEN_VALUE")}
    print("\n".join(line for line in stdout.splitlines() if "_VALUE=" not in line))  # never print secrets

    # The CRM endpoint rejects every webhook until it knows the same secret, and needs an API token and a
    # URL reachable from inside the CRM container to write crm_lead_id back (and for the optional AI agents).
    site_config = {
        "chatwoot_webhook_secret": values["WEBHOOK_SECRET_VALUE"],
        "chatwoot_api_token": values["ADMIN_TOKEN_VALUE"],
        "chatwoot_api_url": "http://chatwoot-rails:3000",
        "chatwoot_platform_token": values["PLATFORM_TOKEN_VALUE"],
    }
    if fb.get("FB_APP_ID") and fb.get("FB_APP_SECRET"):
        site_config["facebook_app_id"] = fb["FB_APP_ID"]
        site_config["facebook_app_secret"] = fb["FB_APP_SECRET"]
    for key, value in site_config.items():
        subprocess.run(
            ["docker", "exec", "-w", "/home/frappe/frappe-bench", "crm-frappe-1",
             "bench", "--site", "crm.localhost", "set-config", key, value],
            check=True, capture_output=True,
        )
    print("CRM site config set: " + ", ".join(site_config))

if __name__ == "__main__":
    main()
