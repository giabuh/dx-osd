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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import demo_catalog

CAT = demo_catalog()

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
        catalog_patch = patch("mmm_custom.api.load_catalog", return_value=CAT)
        catalog_patch.start()
        self.addCleanup(catalog_patch.stop)

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

    def test_unconfigured_secret_rejects_even_the_old_public_default(self):
        # A site without chatwoot_webhook_secret must not fall back to a secret anyone can read in the repo.
        self.conf.pop("chatwoot_webhook_secret")
        ts = str(int(time.time()))
        body = b'{"event": "conversation_created"}'
        self._setup_request(ts=ts, sig=compute_signature("dx_osd_shared_webhook_secret_2026", ts, body), body_bytes=body)
        with patch.object(api_mod, "frappe", self.mock_frappe):
            with self.assertRaises(self.mock_frappe.AuthenticationError):
                chatwoot_sync()

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

    def test_message_created_is_handed_to_the_ai_layer(self):
        # The [I] layer decides itself whether to act (it ignores everything when no API key is set).
        valid_ts = str(int(time.time()))
        payload = {"event": "message_created", "message_type": "incoming", "conversation": {"id": 5}}
        body = json.dumps(payload).encode("utf-8")
        sig = compute_signature(self.secret, valid_ts, body)
        self._setup_request(ts=valid_ts, sig=sig, body_bytes=body)
        with patch.object(api_mod, "frappe", self.mock_frappe), \
                patch.object(api_mod, "enqueue_analysis", return_value={"status": "queued"}) as enqueue:
            res = chatwoot_sync()
        enqueue.assert_called_once_with(payload)
        self.assertEqual(res, {"status": "queued"})

    def test_conversation_updated_goes_to_the_assignment_suggestion(self):
        valid_ts = str(int(time.time()))
        payload = {"event": "conversation_updated", "id": 5, "changed_attributes": []}
        body = json.dumps(payload).encode("utf-8")
        sig = compute_signature(self.secret, valid_ts, body)
        self._setup_request(ts=valid_ts, sig=sig, body_bytes=body)
        with patch.object(api_mod, "frappe", self.mock_frappe), \
                patch.object(api_mod, "enqueue_on_assignment", return_value={"status": "queued"}) as enqueue:
            res = chatwoot_sync()
        enqueue.assert_called_once_with(payload)
        self.assertEqual(res, {"status": "queued"})

    def created(self, contact, messages=(), conv_id=99, lead=("CRM-LEAD-1", False), put=None):
        """Run a conversation_created webhook; the Lead lookup/creation itself is repo.ensure_lead's."""
        payload = {"event": "conversation_created",
                   "conversation": {"id": conv_id, "contact_inbox": {"contact": contact},
                                    "messages": [{"content": m} for m in messages]}}
        body = json.dumps(payload).encode("utf-8")
        ts = str(int(time.time()))
        self._setup_request(ts=ts, sig=compute_signature(self.secret, ts, body), body_bytes=body)
        self.mock_frappe.db.exists.return_value = False  # channel sources not created yet: "Messenger"
        with patch.object(api_mod, "frappe", self.mock_frappe), \
                patch.object(api_mod, "ensure_lead", return_value=lead) as ensure, \
                patch("requests.put", **({"side_effect": put} if put else {})) as mock_put:
            res = chatwoot_sync()
        return res, ensure, mock_put

    def test_a_contact_becomes_one_lead_through_ensure_lead(self):
        contact = {"id": 456, "name": "Tran Van B", "email": "tranb@example.com", "phone_number": "0912345678",
                   "custom_attributes": {"crm_lead_id": "CRM-LEAD-1"}}
        res, ensure, mock_put = self.created(contact, ["Xin chao toi muon tu van"])
        self.assertEqual(res, {"status": "success", "lead_id": "CRM-LEAD-1"})
        ensure.assert_called_once_with(contact, "Messenger", [])
        mock_put.assert_called_once_with(
            "http://127.0.0.1:3000/api/v1/accounts/1/contacts/456",
            headers={"api_access_token": "mock_token_abc"},
            json={"custom_attributes": {"crm_lead_id": "CRM-LEAD-1"}},
            timeout=5,
        )

    def test_courses_named_in_the_first_message_go_to_the_lead(self):
        contact = {"id": 999, "name": "Nguyen Thi D"}
        _, ensure, _ = self.created(contact, ["Chào cô, em muốn đăng ký học AutoCAD cho cháu"])
        self.assertEqual([c.code for c in ensure.call_args[0][2]], ["VKT-CAD2D"])

    def test_the_first_message_is_kept_as_a_note(self):
        self.created({"id": 1, "name": "A"}, ["Dang ky hoc excel"], conv_id=101)
        note = next(c[0][0] for c in self.mock_frappe.get_doc.call_args_list
                    if isinstance(c[0][0], dict) and c[0][0].get("doctype") == "FCRM Note")
        self.assertEqual((note["title"], note["content"], note["reference_docname"]),
                         ("Chatwoot #101", "Dang ky hoc excel", "CRM-LEAD-1"))

    def test_chatwoot_writeback_failure_handled_gracefully(self):
        res, _, _ = self.created({"id": 555, "name": "Hoang D"}, lead=("CRM-LEAD-HOANG-01", True),
                                 put=Exception("Chatwoot offline"))
        # Should succeed and return lead_id despite Chatwoot network error
        self.assertEqual(res, {"status": "success", "lead_id": "CRM-LEAD-HOANG-01"})
        # Error Log titles are capped at 140 chars; a long title raises and rolls the Lead back.
        kwargs = self.mock_frappe.log_error.call_args.kwargs
        self.assertLessEqual(len(kwargs["title"]), 140)
        self.assertIn("Chatwoot offline", kwargs["message"])

    def test_detect_course_interest_from_catalog(self):
        self.assertEqual(detect_course_interest("Em muốn học Excel nâng cao", CAT), "Excel nâng cao & Dashboard")
        self.assertEqual(detect_course_interest("hoc autocad o dau"), "AutoCAD 2D")
        self.assertEqual(detect_course_interest("Robotics cho con 8 tuoi", CAT), "Robotics cơ bản")
        self.assertEqual(detect_course_interest("photoshop va illustrator", CAT), "Photoshop cơ bản, Illustrator")
        for text in ("Xin chào trung tâm!", "Tư vấn học phí giúp em", "", None):
            self.assertIsNone(detect_course_interest(text, CAT))


if __name__ == "__main__":
    unittest.main()
