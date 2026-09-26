#!/usr/bin/env python3
"""End-to-end check of the lead-engine bot (spec 2026-09-26-edu-lead-engine §7.2, D-062).

Sends signed Chatwoot Agent Bot webhooks to a CRM bench and reads back the AI Decision Log rows the
engine writes. Chatwoot does not have to be reachable: failed deliveries are recorded in each row's
`errors`, the decisions are still logged. Meant for a `-p crmverify` bench:

    python scripts/test-bot-conversation.py --url http://127.0.0.1:18000 --secret "$SECRET"
"""

import argparse
import hashlib
import hmac
import json
import sys
import time

import requests

DEFAULT_URL = "http://127.0.0.1:8000"
DEFAULT_HOST = "crm.localhost"


def sign(secret, ts, body):
    return "sha256=" + hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()


class Bench:
    def __init__(self, url, host, secret, user, password):
        self.url, self.host, self.secret = url.rstrip("/"), host, secret
        self.session = requests.Session()
        self.session.headers["Host"] = host
        self.session.post(f"{self.url}/api/method/login", json={"usr": user, "pwd": password}, timeout=15).raise_for_status()
        self.last_id = int(time.time() * 10) % 1_000_000_000
        self.rows = []

    def new_id(self):
        self.last_id += 1
        return self.last_id

    def post(self, conversation_id, contact_id, text, message_id=None, name="Khách Kiểm Thử"):
        message_id = message_id or self.new_id()
        contact = {"id": contact_id, "name": name, "custom_attributes": {}}
        payload = {"event": "message_created", "id": message_id, "content": text, "message_type": "incoming",
                   "private": False, "sender": {**contact, "type": "contact"},
                   "conversation": {"id": conversation_id, "inbox_id": 1, "meta": {"sender": contact}}}
        body, ts = json.dumps(payload).encode(), str(int(time.time()))
        requests.post(f"{self.url}/api/method/mmm_custom.bot_api.agent_bot_webhook", data=body, timeout=15, headers={
            "Host": self.host, "Content-Type": "application/json", "X-Chatwoot-Timestamp": ts,
            "X-Chatwoot-Signature": sign(self.secret, ts, body)}).raise_for_status()
        return message_id

    def logs(self, message_id):
        r = self.session.get(f"{self.url}/api/resource/AI Decision Log", timeout=15, params={
            "filters": json.dumps([["message_id", "=", str(message_id)]]), "fields": json.dumps(["*"]),
            "limit_page_length": 10})
        r.raise_for_status()
        return r.json()["data"]

    def wait(self, message_id, timeout=40):
        deadline = time.time() + timeout
        while time.time() < deadline:
            rows = self.logs(message_id)
            if rows:
                self.rows += rows
                return rows
            time.sleep(0.5)
        raise AssertionError(f"no AI Decision Log row for message {message_id} after {timeout}s — is the RQ worker running?")

    def turn(self, conversation_id, contact_id, text):
        return self.wait(self.post(conversation_id, contact_id, text))[0]

    def conversation(self, conversation_id):
        r = self.session.get(f"{self.url}/api/resource/Bot Conversation/{conversation_id}", timeout=15)
        r.raise_for_status()
        return r.json()["data"]


def check(name, ok, detail):
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + ("" if ok else f"  — {detail}"))
    return bool(ok)


def buttons_only(b, contact):
    """New customer answers only by tapping the first button (typing only what has no buttons)."""
    conv = b.new_id()
    row, turns = b.turn(conv, contact, "xin chào"), 1
    while row["decision_type"] != "handoff" and turns < 12:
        buttons, slot = json.loads(row["reply_buttons"] or "[]"), row["asked_slot"] or ""
        text = buttons[0] if buttons else ("0901 234 567" if "phone" in slot else "9" if "age" in slot else "Lan")
        row, turns = b.turn(conv, contact, text), turns + 1
    doc = b.conversation(conv)
    ok = row["handoff_reason"] == "required_filled" and doc["status"] == "handed_off" and doc.get("lead")
    return check("new customer, buttons only → handoff with a Lead", ok, f"{turns} turns, last: {row['decision_type']} {row['reason']}")


def free_text(b, contact):
    row = b.turn(b.new_id(), contact, "học phí excel ở bình thạnh")
    slots = json.loads(row["slots_after"])
    ok = (row["decision_type"] == "answer" and "fee_quote" in row["skills_answered"]
          and (slots.get("course") or {}).get("value") == "VP-EXCEL"
          and (slots.get("branch") or {}).get("value") == "CN Bình Thạnh" and "1.800.000đ" in row["reply_text"])
    return check("multi-slot free text → fee answer + both slots", ok, json.dumps(row, ensure_ascii=False)[:400])


def returning(b, contact):
    conv = b.new_id()
    row = b.turn(conv, contact, "chào em")
    before = json.loads(row["slots_before"])
    ok = ((before.get("branch") or {}).get("source") == "lead" and (before.get("phone") or {}).get("source") == "lead"
          and row["asked_slot"] == "course" and b.conversation(conv)["is_returning"] == 1)
    return check("returning customer → known facts prefilled, asks only the course", ok, json.dumps(before, ensure_ascii=False))


def duplicate(b, contact):
    conv, mid = b.new_id(), b.new_id()
    b.post(conv, contact, "excel", message_id=mid)
    b.post(conv, contact, "excel", message_id=mid)
    b.wait(mid)
    time.sleep(5)
    rows = b.logs(mid)
    return check("same webhook delivered twice → exactly one reply", len(rows) == 1, f"{len(rows)} log rows")


def jev_disabled(b):
    statuses = {r["jev_status"] for r in b.rows}
    return check("Jev disabled → every turn logged jev_status=disabled", statuses == {"disabled"}, str(statuses))


def main():
    p = argparse.ArgumentParser(description="Lead-engine bot end-to-end check (signed Agent Bot webhooks)")
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--secret", required=True, help="chatwoot_bot_webhook_secret from the site config")
    p.add_argument("--user", default="Administrator")
    p.add_argument("--password", default="admin123")
    a = p.parse_args()
    b = Bench(a.url, a.host, a.secret, a.user, a.password)
    base = b.new_id()
    results = [buttons_only(b, f"t{base}a"), free_text(b, f"t{base}b"), returning(b, f"t{base}a"),
               duplicate(b, f"t{base}c"), jev_disabled(b)]
    print(f"{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
