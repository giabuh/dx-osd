"""Seed branch consultant staff accounts across Chatwoot and Frappe CRM.

Creates 3 consultant accounts (one for each branch) in both Chatwoot and Frappe CRM:
1. CS1 Bình Thạnh: mai.binhthanh@eduflow.vn
2. CS2 Quận 1: nam.quan1@eduflow.vn
3. CS3 Thủ Đức: phuc.thuduc@eduflow.vn

Each agent in Chatwoot is configured with:
- custom_attributes: {"branch": "<branch_key>"}
- Role: agent
- Added to Facebook Messenger inbox (Inbox ID 2) for auto-assignment

Each agent in Frappe CRM is configured with:
- Role: Sales User
- Enabled login
"""

import json
import subprocess
import sys
import urllib.request
import urllib.parse
import http.cookiejar

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

STAFF = [
    {
        "name": "Nguyễn Thị Mai",
        "email": "mai.binhthanh@eduflow.vn",
        "password": "EduFlow@2026",
        "branch": "binh_thanh",
        "branch_name": "CS1 Bình Thạnh",
    },
    {
        "name": "Trần Văn Nam",
        "email": "nam.quan1@eduflow.vn",
        "password": "EduFlow@2026",
        "branch": "quan_1",
        "branch_name": "CS2 Quận 1",
    },
    {
        "name": "Lê Hoàng Phúc",
        "email": "phuc.thuduc@eduflow.vn",
        "password": "EduFlow@2026",
        "branch": "thu_duc",
        "branch_name": "CS3 Thủ Đức",
    },
]


def seed_chatwoot():
    print("=== 1. Seeding Chatwoot Agents ===")
    ruby_script = """
Account.first
inbox = Inbox.find_by(id: 2) || Inbox.where(channel_type: 'Channel::FacebookPage').first

staff_data = JSON.parse(ENV['STAFF_JSON'])
staff_data.each do |s|
  u = User.find_or_initialize_by(email: s['email'])
  u.name = s['name']
  u.password = s['password']
  u.password_confirmation = s['password']
  u.custom_attributes = { 'branch' => s['branch'] }
  u.skip_confirmation! if u.respond_to?(:skip_confirmation!)
  u.save!

  au = AccountUser.find_or_initialize_by(account_id: 1, user_id: u.id)
  au.role = :agent
  au.save!

  if inbox
    im = InboxMember.find_or_initialize_by(inbox_id: inbox.id, user_id: u.id)
    im.save!
  end

  puts "CHATWOOT_OK: #{u.id} | #{u.name} | #{u.email} | branch=#{s['branch']} | inbox_member=#{im&.persisted?}"
end
"""
    cmd = [
        "docker", "exec", "-i",
        "-e", f"STAFF_JSON={json.dumps(STAFF)}",
        "chatwoot-rails-1",
        "bundle", "exec", "rails", "runner", "-"
    ]
    proc = subprocess.run(cmd, input=ruby_script, capture_output=True, text=True, check=True)
    for line in proc.stdout.splitlines():
        if "CHATWOOT_OK" in line:
            print("  [Chatwoot]", line)


def seed_frappe():
    print("\n=== 2. Seeding Frappe CRM Users ===")
    base_url = "http://127.0.0.1:8000"
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    # 1. Login as Administrator
    login_url = f"{base_url}/api/method/login"
    login_data = json.dumps({"usr": "Administrator", "pwd": "admin123"}).encode("utf-8")
    req = urllib.request.Request(
        login_url,
        data=login_data,
        headers={"Host": "crm.localhost", "Content-Type": "application/json"},
    )
    with opener.open(req) as resp:
        if resp.status != 200:
            raise RuntimeError(f"Frappe login failed: {resp.status}")
    print("  [Frappe] Logged in as Administrator")

    # 2. Upsert each staff member
    for s in STAFF:
        email = s["email"]
        user_url = f"{base_url}/api/resource/User/{urllib.parse.quote(email)}"
        req = urllib.request.Request(user_url, headers={"Host": "crm.localhost"})

        user_exists = False
        try:
            with opener.open(req) as resp:
                if resp.status == 200:
                    user_exists = True
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise

        if user_exists:
            update_data = json.dumps({"new_password": s["password"]}).encode("utf-8")
            update_req = urllib.request.Request(
                user_url,
                data=update_data,
                headers={"Host": "crm.localhost", "Content-Type": "application/json"},
                method="PUT",
            )
            with opener.open(update_req) as resp:
                print(f"  [Frappe] Updated password for {email} ({s['name']})")
        else:
            create_data = json.dumps({
                "email": email,
                "first_name": s["name"],
                "send_welcome_email": 0,
                "new_password": s["password"],
                "enabled": 1,
                "roles": [{"role": "Sales User"}],
            }).encode("utf-8")
            create_req = urllib.request.Request(
                f"{base_url}/api/resource/User",
                data=create_data,
                headers={"Host": "crm.localhost", "Content-Type": "application/json"},
                method="POST",
            )
            with opener.open(create_req) as resp:
                print(f"  [Frappe] Created {email} ({s['name']}) with role 'Sales User'")


def main():
    seed_chatwoot()
    seed_frappe()
    print("\n✅ All consultant staff accounts created successfully!")


if __name__ == "__main__":
    main()
