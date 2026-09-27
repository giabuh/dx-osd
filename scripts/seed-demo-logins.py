#!/usr/bin/env python3
"""
scripts/seed-demo-logins.py

Makes the demo logins the same in Frappe CRM and Chatwoot (Chatwoot CE has no SSO):
  - admin@eduflow.vn / admin123 is the admin in both (a System Manager in the CRM);
  - every active CRM consultant signs in to both with their email and one demo password.
Run after the demo dataset is loaded and the staff are synced (scripts/quickstart.sh does it).
Idempotent. Dev/demo only: never run it where the consultants are real staff.

    python3 scripts/seed-demo-logins.py [--password EduFlow@2026] [--keep-admin-password]
"""

import argparse
import json
import subprocess
import sys

DEFAULT_PASSWORD = "EduFlow@2026"  # Chatwoot needs upper + lower + digit + special character

RUBY_SCRIPT = """
require 'json'
account = Account.first
raise 'No account found: run scripts/configure-chatwoot.py first' unless account
data = JSON.parse(STDIN.read)
data['staff'].each do |email|
  user = User.find_by(email: email)
  unless user
    user = User.new(name: email.split('@').first, email: email)
    user.skip_confirmation!
  end
  user.password = data['password']
  user.password_confirmation = data['password']
  user.confirmed_at ||= Time.current
  user.save!
  AccountUser.find_or_create_by!(account: account, user: user) { |au| au.role = :agent }
end
if data['admin']
  admin = User.find_by!(email: data['admin']['email'])
  admin.password = data['admin']['password']
  admin.password_confirmation = data['admin']['password']
  admin.save!(validate: false)  # admin123 is below Chatwoot's password rules, as in configure-chatwoot.py
  puts "CHATWOOT_ADMIN: #{admin.email}"
end
puts "CHATWOOT_STAFF: #{data['staff'].size}"
"""


def crm_apply(password):
    proc = subprocess.run(
        ["docker", "exec", "-w", "/home/frappe/frappe-bench", "crm-frappe-1",
         "bench", "--site", "crm.localhost", "execute", "mmm_custom.demo.logins.apply",
         "--kwargs", json.dumps({"staff_password": password})],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        sys.exit(proc.returncode)
    return json.loads(proc.stdout.strip().splitlines()[-1])


def chatwoot_apply(emails, password, admin):
    # Ruby comes through `-e` so STDIN stays free for the JSON (keeps the password off the command line).
    proc = subprocess.run(
        ["docker", "exec", "-i", "chatwoot-rails-1", "bundle", "exec", "rails", "runner", RUBY_SCRIPT],
        input=json.dumps({"staff": emails, "password": password, "admin": admin}), capture_output=True, text=True,
    )
    if proc.returncode != 0:
        print(proc.stderr, file=sys.stderr)
        sys.exit(proc.returncode)
    print("\n".join(line for line in proc.stdout.splitlines() if line.startswith("CHATWOOT_")))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help=f"staff demo password (default: {DEFAULT_PASSWORD})")
    parser.add_argument("--keep-admin-password", action="store_true",
                        help="leave the Chatwoot admin's current password as it is")
    args = parser.parse_args()

    result = crm_apply(args.password)
    print(f"CRM: admin {result['admin']}, {len(result['staff'])} consultants")
    admin = None if args.keep_admin_password else {"email": result["admin"], "password": result["admin_password"]}
    chatwoot_apply(result["staff"], args.password, admin)
    print(f"Sign in to both apps with {result['admin']} / admin123, or any consultant email / {args.password}")


if __name__ == "__main__":
    main()
