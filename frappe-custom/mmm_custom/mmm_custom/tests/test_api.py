import hashlib
import hmac
import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

# Ensure mmm_custom package is importable when running unittest standalone
APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

if "requests" not in sys.modules:
    mock_requests_mod = MagicMock()
    sys.modules["requests"] = mock_requests_mod

import mmm_custom.api as api_mod
from mmm_custom.api import chatwoot_sync, detect_course_interest


def compute_signature(secret: str, ts: str, body: bytes) -> str:
    msg = f"{ts}.".encode("utf-8") + body
    return "sha256=" + hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


class TestChatwootSyncApi(unittest.TestCase):
    def setUp(self):
        self.secret = "test_webhook_secret_xyz"
        self.conf = {
            "chatwoot_webhook_secret": self.secret,
            "chatwoot_api_token": "mock_token_abc",
            "chatwoot_api_url": "http://127.0.0.1:3000",
        }
        self.mock_frappe = MagicMock()
        self.mock_frappe.conf = self.conf
        self.mock_frappe.AuthenticationError = api_mod.frappe.AuthenticationError
        self.mock_frappe.throw = api_mod.frappe.throw

    def _setup_request(self, ts=None, sig=None, body_bytes=b""):
        mock_req = MagicMock()
        headers = {}
        if ts is not None:
            headers["X-Chatwoot-Timestamp"] = str(ts)
        if sig is not None:
            headers["X-Chatwoot-Signature"] = str(sig)
        mock_req.headers = headers
        mock_req.get_data.return_value = body_bytes
        mock_req.data = body_bytes
        self.mock_frappe.request = mock_req

    def test_missing_timestamp_raises(self):
        self._setup_request(ts=None, sig="dummy_sig", body_bytes=b"{}")
        with patch.object(api_mod, "frappe", self.mock_frappe):
            with self.assertRaises(self.mock_frappe.AuthenticationError):
                chatwoot_sync()

    def test_invalid_timestamp_string_raises(self):
        self._setup_request(ts="not-a-number", sig="dummy_sig", body_bytes=b"{}")
        with patch.object(api_mod, "frappe", self.mock_frappe):
            with self.assertRaises(self.mock_frappe.AuthenticationError):
                chatwoot_sync()

    def test_expired_timestamp_past_raises(self):
        expired_ts = str(int(time.time()) - 301)
        sig = compute_signature(self.secret, expired_ts, b"{}")
        self._setup_request(ts=expired_ts, sig=sig, body_bytes=b"{}")
        with patch.object(api_mod, "frappe", self.mock_frappe):
            with self.assertRaises(self.mock_frappe.AuthenticationError):
                chatwoot_sync()

    def test_future_timestamp_expired_raises(self):
        future_ts = str(int(time.time()) + 301)
        sig = compute_signature(self.secret, future_ts, b"{}")
        self._setup_request(ts=future_ts, sig=sig, body_bytes=b"{}")
        with patch.object(api_mod, "frappe", self.mock_frappe):
            with self.assertRaises(self.mock_frappe.AuthenticationError):
                chatwoot_sync()

    def test_invalid_hmac_signature_raises(self):
        valid_ts = str(int(time.time()))
        self._setup_request(ts=valid_ts, sig="sha256=invalid_hash", body_bytes=b'{"event":"test"}')
        with patch.object(api_mod, "frappe", self.mock_frappe):
            with self.assertRaises(self.mock_frappe.AuthenticationError):
                chatwoot_sync()

    def test_valid_hmac_signature_passes(self):
        valid_ts = str(int(time.time()))
        body = json.dumps({"event": "other_event"}).encode("utf-8")
        sig = compute_signature(self.secret, valid_ts, body)
        self._setup_request(ts=valid_ts, sig=sig, body_bytes=body)
        with patch.object(api_mod, "frappe", self.mock_frappe):
            res = chatwoot_sync()
            self.assertEqual(res, {"status": "ignored", "event": "other_event"})

    def test_valid_hmac_signature_without_sha256_prefix(self):
        valid_ts = str(int(time.time()))
        body = json.dumps({"event": "other_event"}).encode("utf-8")
        sig = compute_signature(self.secret, valid_ts, body).replace("sha256=", "")
        self._setup_request(ts=valid_ts, sig=sig, body_bytes=body)
        with patch.object(api_mod, "frappe", self.mock_frappe):
            res = chatwoot_sync()
            self.assertEqual(res, {"status": "ignored", "event": "other_event"})

    def test_invalid_json_body_returns_error(self):
        valid_ts = str(int(time.time()))
        body = b"not a json string"
        sig = compute_signature(self.secret, valid_ts, body)
        self._setup_request(ts=valid_ts, sig=sig, body_bytes=body)
        with patch.object(api_mod, "frappe", self.mock_frappe):
            res = chatwoot_sync()
            self.assertEqual(res, {"status": "error", "message": "Invalid JSON body"})

    def test_non_conversation_created_event_ignored(self):
        valid_ts = str(int(time.time()))
        body = json.dumps({"event": "message_created"}).encode("utf-8")
        sig = compute_signature(self.secret, valid_ts, body)
        self._setup_request(ts=valid_ts, sig=sig, body_bytes=body)
        with patch.object(api_mod, "frappe", self.mock_frappe):
            res = chatwoot_sync()
            self.assertEqual(res, {"status": "ignored", "event": "message_created"})

    def test_existing_crm_lead_id_in_crm(self):
        valid_ts = str(int(time.time()))
        payload = {
            "event": "conversation_created",
            "conversation": {
                "id": 99,
                "contact_inbox": {
                    "contact": {
                        "id": 456,
                        "name": "Tran Van B",
                        "email": "tranb@example.com",
                        "phone_number": "0912345678",
                        "custom_attributes": {"crm_lead_id": "CRM-LEAD-EXISTING-01"},
                    }
                },
                "messages": [{"content": "Xin chao toi muon tu van"}],
            },
        }
        body = json.dumps(payload).encode("utf-8")
        sig = compute_signature(self.secret, valid_ts, body)
        self._setup_request(ts=valid_ts, sig=sig, body_bytes=body)

        self.mock_frappe.db.exists.return_value = True
        mock_note = MagicMock()
        self.mock_frappe.get_doc.return_value = mock_note

        with patch.object(api_mod, "frappe", self.mock_frappe):
            with patch("requests.put") as mock_put:
                res = chatwoot_sync()
                self.assertEqual(res, {"status": "success", "lead_id": "CRM-LEAD-EXISTING-01"})
                self.mock_frappe.db.exists.assert_called_once_with("CRM Lead", "CRM-LEAD-EXISTING-01")
                self.mock_frappe.db.set_value.assert_called_with("CRM Lead", "CRM-LEAD-EXISTING-01", "chatwoot_contact_id", "456")
                mock_note.insert.assert_called_once()
                mock_put.assert_called_once_with(
                    "http://127.0.0.1:3000/api/v1/accounts/1/contacts/456",
                    headers={"api_access_token": "mock_token_abc"},
                    json={"custom_attributes": {"crm_lead_id": "CRM-LEAD-EXISTING-01"}},
                    timeout=5,
                )

    def test_matched_lead_by_email_or_phone(self):
        valid_ts = str(int(time.time()))
        payload = {
            "event": "conversation_created",
            "conversation": {
                "id": 101,
                "contact_inbox": {
                    "contact": {
                        "id": 789,
                        "name": "Le Thi C",
                        "email": "lethic@example.com",
                        "phone_number": "0987654321",
                        "custom_attributes": {},
                    }
                },
                "messages": [{"content": "Dang ky hoc tieng Anh"}],
            },
        }
        body = json.dumps(payload).encode("utf-8")
        sig = compute_signature(self.secret, valid_ts, body)
        self._setup_request(ts=valid_ts, sig=sig, body_bytes=body)

        self.mock_frappe.db.exists.return_value = False
        matched_lead = {"name": "CRM-LEAD-MATCHED-99"}

        with patch.object(api_mod, "frappe", self.mock_frappe):
            with patch("mmm_custom.api.find_matching_lead", return_value=matched_lead) as mock_find:
                with patch("requests.put") as mock_put:
                    res = chatwoot_sync()
                    self.assertEqual(res, {"status": "success", "lead_id": "CRM-LEAD-MATCHED-99"})
                    mock_find.assert_called_once_with("lethic@example.com", "0987654321")
                    self.mock_frappe.db.set_value.assert_any_call("CRM Lead", "CRM-LEAD-MATCHED-99", "chatwoot_contact_id", "789")
                    self.mock_frappe.db.set_value.assert_any_call("CRM Lead", "CRM-LEAD-MATCHED-99", "course_interest", "Tiếng Anh")
                    mock_put.assert_called_once()

    def test_create_new_lead_when_no_match(self):
        valid_ts = str(int(time.time()))
        payload = {
            "event": "conversation_created",
            "conversation": {
                "id": 102,
                "contact_inbox": {
                    "contact": {
                        "id": 888,
                        "name": "",  # Empty name -> should fallback to "EduFlow Student"
                        "email": "newbie@example.com",
                        "phone_number": "0901234567",
                    }
                },
                "messages": [],
            },
        }
        body = json.dumps(payload).encode("utf-8")
        sig = compute_signature(self.secret, valid_ts, body)
        self._setup_request(ts=valid_ts, sig=sig, body_bytes=body)

        self.mock_frappe.db.exists.return_value = False
        mock_lead_doc = MagicMock()
        mock_lead_doc.name = "CRM-LEAD-NEW-001"
        mock_lead_doc.insert.return_value = mock_lead_doc
        self.mock_frappe.get_doc.return_value = mock_lead_doc

        with patch.object(api_mod, "frappe", self.mock_frappe):
            with patch("mmm_custom.api.find_matching_lead", return_value=None):
                with patch("requests.put") as mock_put:
                    res = chatwoot_sync()
                    self.assertEqual(res, {"status": "success", "lead_id": "CRM-LEAD-NEW-001"})
                    self.mock_frappe.get_doc.assert_any_call({
                        "doctype": "CRM Lead",
                        "first_name": "EduFlow Student",
                        "email": "newbie@example.com",
                        "mobile_no": "+84901234567",
                        "source": "Messenger",
                        "chatwoot_contact_id": "888",
                    })
                    mock_lead_doc.insert.assert_called()
                    mock_put.assert_called_once()

    def test_chatwoot_writeback_failure_handled_gracefully(self):
        valid_ts = str(int(time.time()))
        payload = {
            "event": "conversation_created",
            "conversation": {
                "id": 103,
                "contact_inbox": {
                    "contact": {
                        "id": 555,
                        "name": "Hoang D",
                        "email": "hoang@example.com",
                        "phone_number": "0911223344",
                    }
                },
            },
        }
        body = json.dumps(payload).encode("utf-8")
        sig = compute_signature(self.secret, valid_ts, body)
        self._setup_request(ts=valid_ts, sig=sig, body_bytes=body)

        mock_lead = MagicMock()
        mock_lead.name = "CRM-LEAD-HOANG-01"
        mock_lead.insert.return_value = mock_lead
        self.mock_frappe.get_doc.return_value = mock_lead

        with patch.object(api_mod, "frappe", self.mock_frappe):
            with patch("mmm_custom.api.find_matching_lead", return_value=None):
                with patch("requests.put", side_effect=Exception("Chatwoot offline")):
                    res = chatwoot_sync()
                    # Should succeed and return lead_id despite Chatwoot network error
                    self.assertEqual(res, {"status": "success", "lead_id": "CRM-LEAD-HOANG-01"})
                    self.mock_frappe.log_error.assert_called()

    def test_detect_course_interest_various_keywords(self):
        # Tiếng Anh
        self.assertEqual(detect_course_interest("Em muốn học tiếng Anh cho bé"), "Tiếng Anh")
        self.assertEqual(detect_course_interest("Dang ky lop tieng anh giao tiep"), "Tiếng Anh")
        self.assertEqual(detect_course_interest("Do you offer English courses?"), "Tiếng Anh")

        # Bơi lội
        self.assertEqual(detect_course_interest("Học bơi lội vào mùa hè"), "Bơi lội")
        self.assertEqual(detect_course_interest("Lớp học bơi cho trẻ em"), "Bơi lội")
        self.assertEqual(detect_course_interest("Interested in swimming lessons"), "Bơi lội")
        self.assertEqual(detect_course_interest("dang ky lop boi loi"), "Bơi lội")

        # Toán tư duy
        self.assertEqual(detect_course_interest("Tư vấn khóa học Toán tư duy"), "Toán tư duy")
        self.assertEqual(detect_course_interest("Học toán cho học sinh cấp 1"), "Toán tư duy")
        self.assertEqual(detect_course_interest("Lớp toan tu duy"), "Toán tư duy")
        self.assertEqual(detect_course_interest("Do you have math class?"), "Toán tư duy")

        # Negative / No match
        self.assertIsNone(detect_course_interest("Xin chào trung tâm!"))
        self.assertIsNone(detect_course_interest("Tư vấn học phí giúp em"))
        self.assertIsNone(detect_course_interest("Tôi hoàn toàn đồng ý"))
        self.assertIsNone(detect_course_interest(""))
        self.assertIsNone(detect_course_interest(None))

    def test_create_new_lead_with_course_interest(self):
        valid_ts = str(int(time.time()))
        payload = {
            "event": "conversation_created",
            "conversation": {
                "id": 104,
                "contact_inbox": {
                    "contact": {
                        "id": 999,
                        "name": "Nguyen Thi D",
                        "email": "nguyend@example.com",
                        "phone_number": "0933445566",
                    }
                },
                "messages": [{"content": "Chào cô, em muốn đăng ký học toán tư duy cho cháu"}],
            },
        }
        body = json.dumps(payload).encode("utf-8")
        sig = compute_signature(self.secret, valid_ts, body)
        self._setup_request(ts=valid_ts, sig=sig, body_bytes=body)

        self.mock_frappe.db.exists.return_value = False
        mock_lead_doc = MagicMock()
        mock_lead_doc.name = "CRM-LEAD-MATH-001"
        mock_lead_doc.insert.return_value = mock_lead_doc
        self.mock_frappe.get_doc.return_value = mock_lead_doc

        with patch.object(api_mod, "frappe", self.mock_frappe):
            with patch("mmm_custom.api.find_matching_lead", return_value=None):
                with patch("requests.put"):
                    res = chatwoot_sync()
                    self.assertEqual(res, {"status": "success", "lead_id": "CRM-LEAD-MATH-001"})
                    self.mock_frappe.get_doc.assert_any_call({
                        "doctype": "CRM Lead",
                        "first_name": "Nguyen Thi D",
                        "email": "nguyend@example.com",
                        "mobile_no": "+84933445566",
                        "source": "Messenger",
                        "chatwoot_contact_id": "999",
                        "course_interest": "Toán tư duy",
                    })

    def test_existing_lead_updates_course_interest(self):
        valid_ts = str(int(time.time()))
        payload = {
            "event": "conversation_created",
            "conversation": {
                "id": 105,
                "contact_inbox": {
                    "contact": {
                        "id": 456,
                        "name": "Tran Van B",
                        "email": "tranb@example.com",
                        "phone_number": "0912345678",
                        "custom_attributes": {"crm_lead_id": "CRM-LEAD-EXISTING-01"},
                    }
                },
                "messages": [{"content": "Toi muon cho con hoc boi loi"}],
            },
        }
        body = json.dumps(payload).encode("utf-8")
        sig = compute_signature(self.secret, valid_ts, body)
        self._setup_request(ts=valid_ts, sig=sig, body_bytes=body)

        self.mock_frappe.db.exists.return_value = True
        mock_note = MagicMock()
        self.mock_frappe.get_doc.return_value = mock_note

        with patch.object(api_mod, "frappe", self.mock_frappe):
            with patch("requests.put"):
                res = chatwoot_sync()
                self.assertEqual(res, {"status": "success", "lead_id": "CRM-LEAD-EXISTING-01"})
                self.mock_frappe.db.set_value.assert_any_call("CRM Lead", "CRM-LEAD-EXISTING-01", "chatwoot_contact_id", "456")
                self.mock_frappe.db.set_value.assert_any_call("CRM Lead", "CRM-LEAD-EXISTING-01", "course_interest", "Bơi lội")


if __name__ == "__main__":
    unittest.main()
