#!/usr/bin/env python3
"""
scripts/refresh-facebook-token.py

Utility to validate, exchange, and save Facebook Page Access Tokens.
Updates both .env and Frappe CRM site_config.json automatically.

Usage:
    python scripts/refresh-facebook-token.py --token <NEW_PAGE_ACCESS_TOKEN>
    python scripts/refresh-facebook-token.py --user-token <USER_TOKEN> --app-id <APP_ID> --app-secret <APP_SECRET>
"""

import argparse
import json
import os
import subprocess
import sys
import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PAGE_ID = "1334466483083776"


def update_env_file(key: str, value: str):
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    lines = []
    found = False
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

    new_lines = []
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}\n")
            found = True
        else:
            new_lines.append(line)

    if not found:
        new_lines.append(f"{key}={value}\n")

    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)
    print(f"✅ Updated {key} in .env")


def update_crm_site_config(token: str):
    cmd = [
        "docker", "exec", "crm-frappe-1",
        "bench", "--site", "crm.localhost", "set-config", "facebook_page_access_token", token
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0:
        print("✅ Updated facebook_page_access_token in Frappe CRM site_config.json")
    else:
        print(f"⚠️ Failed to update site_config.json: {res.stderr}")


def check_token(token: str) -> dict:
    url = f"https://graph.facebook.com/v21.0/me?access_token={token}&fields=id,name"
    resp = requests.get(url, timeout=15)
    return resp.json()


def get_permanent_page_token(user_token: str, app_id: str, app_secret: str, page_id: str) -> str | None:
    # 1. Exchange for long-lived user token
    exchange_url = "https://graph.facebook.com/v21.0/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": app_id,
        "client_secret": app_secret,
        "fb_exchange_token": user_token,
    }
    r = requests.get(exchange_url, params=params, timeout=20)
    data = r.json()
    if "access_token" not in data:
        print(f"❌ Failed to exchange long-lived token: {data}")
        return None

    long_user_token = data["access_token"]
    print("✨ Successfully obtained 60-day Long-Lived User Token!")

    # 2. Get permanent Page Token via /me/accounts
    acc_url = f"https://graph.facebook.com/v21.0/me/accounts?access_token={long_user_token}"
    r_acc = requests.get(acc_url, timeout=20)
    acc_data = r_acc.json()
    for p in acc_data.get("data", []):
        if str(p.get("id")) == str(page_id):
            print(f"🎉 Found Page '{p.get('name')}'! Generated permanent Page Access Token.")
            return p.get("access_token")

    print(f"❌ Page ID {page_id} not found in user accounts list: {[p.get('id') for p in acc_data.get('data', [])]}")
    return None


def main():
    parser = argparse.ArgumentParser(description="Update Facebook Page Access Token")
    parser.add_argument("--token", help="Direct Page Access Token from Graph API Explorer")
    parser.add_argument("--user-token", help="User Access Token to convert into permanent Page Token")
    parser.add_argument("--app-id", help="Facebook App ID")
    parser.add_argument("--app-secret", help="Facebook App Secret")
    args = parser.parse_args()

    page_token = args.token

    if args.user_token and args.app_id and args.app_secret:
        page_token = get_permanent_page_token(args.user_token, args.app_id, args.app_secret, PAGE_ID)

    if not page_token:
        print("❌ No token provided or token generation failed.")
        sys.exit(1)

    # Verify token
    info = check_token(page_token)
    if "error" in info:
        print(f"❌ Token validation failed: {info['error'].get('message')}")
        sys.exit(1)

    print(f"✅ Token is valid for: {info.get('name')} (ID: {info.get('id')})")

    # Save token
    update_env_file("FACEBOOK_PAGE_ACCESS_TOKEN", page_token)
    update_crm_site_config(page_token)

    # Update Chatwoot if available
    try:
        subprocess.run(["python", "scripts/setup-facebook-channel.py", page_token], capture_output=True)
        print("✅ Updated Chatwoot Facebook Channel")
    except Exception:
        pass

    # Clear bench cache
    subprocess.run(["docker", "exec", "crm-frappe-1", "bench", "--site", "crm.localhost", "clear-cache"], capture_output=True)
    print("🚀 All services updated with new Facebook token!")


if __name__ == "__main__":
    main()
