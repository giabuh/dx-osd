#!/usr/bin/env python3
"""
scripts/test-chatwoot-crm-sync.py

End-to-end verification script for Chatwoot -> Frappe CRM webhook sync:
- Verifies HMAC-SHA256 signature calculation and anti-replay timestamp verification.
- Tests invalid signature rejection (HTTP 401 / 403).
- Tests expired timestamp rejection (HTTP 401 / 403).
- Tests new Lead creation for student "Hoàng Thành" (phone "0901234567").
- Tests lead convergence: subsequent webhook updates existing lead without duplicating.
- Tests non-conversation_created event handling.
"""

import argparse
import hashlib
import hmac
import json
import sys
import time
import urllib.error
import urllib.request

DEFAULT_CRM_URL = "http://127.0.0.1:8000/api/method/mmm_custom.api.chatwoot_sync"
DEFAULT_SECRET = "dx_osd_shared_webhook_secret_2026"
DEFAULT_HOST = "crm.localhost"


def compute_signature(secret: str, timestamp: str, body_bytes: bytes) -> str:
    secret_bytes = secret.encode("utf-8")
    to_sign = f"{timestamp}.".encode("utf-8") + body_bytes
    digest = hmac.new(secret_bytes, to_sign, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def make_request(
    url: str,
    payload: dict,
    secret: str,
    timestamp: str = None,
    signature: str = None,
    host_header: str = DEFAULT_HOST,
    timeout: int = 10,
):
    body_bytes = json.dumps(payload).encode("utf-8")
    if timestamp is None:
        timestamp = str(int(time.time()))
    if signature is None:
        signature = compute_signature(secret, timestamp, body_bytes)

    headers = {
        "Content-Type": "application/json",
        "X-Chatwoot-Timestamp": timestamp,
        "X-Chatwoot-Signature": signature,
    }
    if host_header:
        headers["Host"] = host_header

    req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status_code = resp.getcode()
            raw_response = resp.read().decode("utf-8")
            try:
                parsed_json = json.loads(raw_response)
            except Exception:
                parsed_json = {"raw": raw_response}
            return status_code, parsed_json
    except urllib.error.HTTPError as e:
        status_code = e.code
        raw_response = e.read().decode("utf-8", errors="replace")
        try:
            parsed_json = json.loads(raw_response)
        except Exception:
            parsed_json = {"raw": raw_response}
        return status_code, parsed_json
    except Exception as e:
        return 0, {"error": str(e)}


def build_chatwoot_payload(
    event: str = "conversation_created",
    conv_id: int = 101,
    contact_id: int = 202,
    name: str = "Hoàng Thành",
    email: str = "hoangthanh@eduflow.vn",
    phone: str = "0901234567",
    content: str = "Em muốn đăng ký khoá học EduFlow Fullstack",
    crm_lead_id: str = None,
) -> dict:
    custom_attrs = {}
    if crm_lead_id:
        custom_attrs["crm_lead_id"] = crm_lead_id

    return {
        "event": event,
        "id": conv_id,
        "conversation": {
            "id": conv_id,
            "status": "open",
            "messages": [
                {
                    "id": 501,
                    "content": content,
                    "message_type": "incoming",
                }
            ],
            "contact_inbox": {
                "id": 301,
                "contact": {
                    "id": contact_id,
                    "name": name,
                    "email": email,
                    "phone_number": phone,
                    "custom_attributes": custom_attrs,
                },
            },
        },
    }


def run_tests(url: str, secret: str, host: str):
    print("=" * 70)
    print("DX-OSD: Chatwoot -> Frappe CRM Webhook Sync Verification")
    print(f"Target URL: {url}")
    print(f"Host Header: {host}")
    print("=" * 70)

    passed_tests = 0
    total_tests = 5

    # Test 1: Invalid HMAC signature rejected
    print("\n[Test 1/5] Testing Invalid HMAC Signature Rejection...")
    payload_test1 = build_chatwoot_payload()
    bad_signature = "sha256=0000000000000000000000000000000000000000000000000000000000000000"
    ts = str(int(time.time()))
    code, resp = make_request(
        url, payload_test1, secret, timestamp=ts, signature=bad_signature, host_header=host
    )
    if code in (401, 403):
        print(f"  [PASS] Server rejected invalid signature with HTTP {code}.")
        passed_tests += 1
    else:
        print(f"  [FAIL] Expected HTTP 401/403, got HTTP {code}: {resp}")

    # Test 2: Expired timestamp rejected (> 300 seconds ago)
    print("\n[Test 2/5] Testing Expired Timestamp Anti-Replay...")
    payload_test2 = build_chatwoot_payload()
    expired_ts = str(int(time.time()) - 400)
    code, resp = make_request(
        url, payload_test2, secret, timestamp=expired_ts, host_header=host
    )
    if code in (401, 403):
        print(f"  [PASS] Server rejected expired timestamp with HTTP {code}.")
        passed_tests += 1
    else:
        print(f"  [FAIL] Expected HTTP 401/403, got HTTP {code}: {resp}")

    # Test 3: New conversation with student "Hoàng Thành"
    print("\n[Test 3/5] Testing New Lead Creation (Hoàng Thành)...")
    payload_test3 = build_chatwoot_payload(
        event="conversation_created",
        conv_id=101,
        contact_id=202,
        name="Hoàng Thành",
        email="hoangthanh@eduflow.vn",
        phone="0901234567",
        content="Em muốn đăng ký khoá học EduFlow Fullstack",
    )
    code, resp = make_request(url, payload_test3, secret, host_header=host)
    lead_id_1 = None
    if code == 200 and isinstance(resp, dict):
        msg = resp.get("message", {})
        if msg.get("status") == "success" and msg.get("lead_id"):
            lead_id_1 = msg.get("lead_id")
            print(f"  [PASS] Lead successfully created in Frappe CRM. Lead ID: '{lead_id_1}'")
            passed_tests += 1
        else:
            print(f"  [FAIL] HTTP 200 but unexpected body: {resp}")
    else:
        print(f"  [FAIL] Expected HTTP 200, got HTTP {code}: {resp}")

    # Test 4: Lead convergence / deduplication on repeated conversation
    print("\n[Test 4/5] Testing Lead Convergence (No Duplicate)...")
    payload_test4 = build_chatwoot_payload(
        event="conversation_created",
        conv_id=102,
        contact_id=202,
        name="Hoàng Thành",
        email="hoangthanh@eduflow.vn",
        phone="0901234567",
        content="Em muốn hỏi thêm về lịch học cuối tuần",
        crm_lead_id=lead_id_1,
    )
    code, resp = make_request(url, payload_test4, secret, host_header=host)
    if code == 200 and isinstance(resp, dict):
        msg = resp.get("message", {})
        lead_id_2 = msg.get("lead_id")
        if msg.get("status") == "success" and lead_id_2:
            if lead_id_1 and lead_id_2 == lead_id_1:
                print(f"  [PASS] Convergence verified! Matched existing Lead ID: '{lead_id_2}' (no duplicate created)")
                passed_tests += 1
            elif not lead_id_1:
                print(f"  [PASS] Returned Lead ID: '{lead_id_2}'")
                passed_tests += 1
            else:
                print(f"  [FAIL] Convergence failed! Created duplicate lead: '{lead_id_2}' != '{lead_id_1}'")
        else:
            print(f"  [FAIL] HTTP 200 but unexpected body: {resp}")
    else:
        print(f"  [FAIL] Expected HTTP 200, got HTTP {code}: {resp}")

    # Test 5: Ignored non-conversation_created event
    print("\n[Test 5/5] Testing Ignored Non-Conversation Event...")
    payload_test5 = build_chatwoot_payload(event="conversation_status_changed")
    code, resp = make_request(url, payload_test5, secret, host_header=host)
    if code == 200 and isinstance(resp, dict):
        msg = resp.get("message", {})
        if msg.get("status") == "ignored":
            print(f"  [PASS] Event correctly ignored: {msg.get('event')}")
            passed_tests += 1
        else:
            print(f"  [FAIL] Expected status 'ignored', got: {resp}")
    else:
        print(f"  [FAIL] Expected HTTP 200, got HTTP {code}: {resp}")

    print("\n" + "=" * 70)
    print(f"Summary: {passed_tests}/{total_tests} tests passed.")
    print("=" * 70)
    return passed_tests == total_tests


def main():
    parser = argparse.ArgumentParser(description="Test Chatwoot -> Frappe CRM sync webhook")
    parser.add_argument("--url", default=DEFAULT_CRM_URL, help=f"CRM Webhook URL (default: {DEFAULT_CRM_URL})")
    parser.add_argument("--secret", default=DEFAULT_SECRET, help=f"HMAC secret (default: {DEFAULT_SECRET})")
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Host header (default: {DEFAULT_HOST})")
    args = parser.parse_args()

    success = run_tests(url=args.url, secret=args.secret, host=args.host)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
