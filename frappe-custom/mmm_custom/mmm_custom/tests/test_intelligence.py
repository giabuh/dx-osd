import re
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

if "requests" not in sys.modules:
    sys.modules["requests"] = MagicMock()

import mmm_custom.intelligence as intel
from mmm_custom.intelligence import (
    DEFAULT_REPLY_TEMPLATES,
    HOTNESS,
    INTENTS,
    build_questions,
    decide_actions,
    find_candidates,
)

TEMPLATES = {"send_price": "Dạ bên em gửi bảng giá ạ", "ask_phone": "Anh/chị cho em xin SĐT ạ"}
CONFIDENT = {
    "intent": {"choice": "price_inquiry", "confidence": 0.9},
    "hotness": {"score": 2, "confidence": 0.8},
    "phone": {"choice": "+84901234567", "confidence": 0.95},
    "reply": {"choice": "send_price", "confidence": 0.85},
}
EMPTY_LEAD = {"mobile_no": "", "email": ""}


class TestPureLogic(unittest.TestCase):
    def test_intent_and_hotness_keys_match_the_select_options_in_setup(self):
        setup = (APP_DIR / "mmm_custom" / "setup.py").read_text(encoding="utf-8")

        def options(field):
            return [o for o in re.search(rf'"fieldname": "{field}"[\s\S]*?"options": "([^"]*)"', setup).group(1).split("\\n") if o]

        self.assertEqual(options("ai_intent"), list(INTENTS))
        self.assertEqual(options("ai_hotness"), HOTNESS)

    def test_find_candidates_normalizes_common_vietnamese_spellings_and_dedupes(self):
        c = find_candidates(["sđt em 0901 234 567 nhé", "hoặc 090.123.4567", "mail: An.Nguyen@Gmail.com", "số +84 912 345 678"])
        self.assertEqual(c["phones"], ["+84901234567", "+84912345678"])
        self.assertEqual(c["emails"], ["an.nguyen@gmail.com"])

    def test_find_candidates_ignores_order_numbers_and_prices(self):
        self.assertEqual(find_candidates(["đơn #12345, học phí 3.500.000đ"])["phones"], [])

    def test_build_questions_only_asks_what_there_is_to_choose(self):
        bare = build_questions({"phones": [], "emails": []}, {})
        self.assertEqual(list(bare), ["intent", "hotness"])
        full = build_questions({"phones": ["+84901234567"], "emails": ["a@b.com"]}, TEMPLATES)
        self.assertEqual(list(full), ["intent", "hotness", "phone", "email", "reply"])
        self.assertEqual(list(full["phone"]["criteria"]), ["+84901234567", "none"])
        self.assertEqual(len(full["hotness"]["criteria"]), len(HOTNESS))

    def test_confident_answers_update_the_lead_label_and_suggest_a_reply(self):
        plan = decide_actions(CONFIDENT, TEMPLATES, 0.7, EMPTY_LEAD)
        self.assertEqual(plan["lead_update"], {"ai_intent": "price_inquiry", "ai_hotness": "hot", "mobile_no": "+84901234567"})
        self.assertEqual(plan["labels"], ["ai-price_inquiry", "hot"])
        self.assertIn("độ tin cậy 0.85", plan["reply_note"])
        self.assertIn("bảng giá", plan["reply_note"])
        self.assertEqual(plan["skipped"], [])

    def test_nothing_is_applied_below_the_threshold(self):
        unsure = {k: {**v, "confidence": 0.4} for k, v in CONFIDENT.items()}
        plan = decide_actions(unsure, TEMPLATES, 0.7, EMPTY_LEAD)
        self.assertEqual(plan["lead_update"], {})
        self.assertEqual(plan["labels"], [])
        self.assertIsNone(plan["reply_note"])
        self.assertEqual(plan["skipped"], ["intent", "hotness", "phone", "reply"])

    def test_never_overwrites_a_phone_the_lead_already_has(self):
        plan = decide_actions(CONFIDENT, TEMPLATES, 0.7, {"mobile_no": "+84999999999", "email": ""})
        self.assertNotIn("mobile_no", plan["lead_update"])

    def test_spam_gets_no_reply_and_its_phone_is_never_copied(self):
        # Real Jev run: an ad for "tăng like" was spam (0.87) and its Zalo number scored 0.69 as "the customer's own".
        answers = {**CONFIDENT, "intent": {"choice": "spam", "confidence": 0.87}}
        plan = decide_actions(answers, TEMPLATES, 0.7, EMPTY_LEAD)
        self.assertEqual(plan["lead_update"]["ai_intent"], "spam")
        self.assertNotIn("mobile_no", plan["lead_update"])
        self.assertIsNone(plan["reply_note"])


def conversation(contact_attrs=None, contact_id=42):
    return {
        "meta": {"labels": [], "contact": {"id": contact_id, "custom_attributes": contact_attrs or {}}},
        "payload": [
            {"message_type": 0, "private": False, "content": "Cho em hỏi học phí lớp tiếng Anh"},
            {"message_type": 1, "private": False, "content": "Dạ bé mấy tuổi ạ"},
            {"message_type": 1, "private": True, "content": "internal note"},
            {"message_type": 2, "private": False, "content": "Conversation assigned"},
            {"message_type": 0, "private": False, "content": "8 tuổi, sđt em 0901234567"},
        ],
    }


class TestEnqueue(unittest.TestCase):
    def setUp(self):
        self.frappe = MagicMock()
        self.frappe.conf = {"typesafe_api_key": "k"}

    def test_queues_incoming_messages(self):
        with patch.object(intel, "frappe", self.frappe):
            result = intel.enqueue_analysis({"event": "message_created", "message_type": "incoming", "conversation": {"id": 5}})
        self.assertEqual(result["status"], "queued")
        self.frappe.enqueue.assert_called_once_with("mmm_custom.intelligence.analyze_conversation", queue="long", conversation_id=5, suggest_reply=True)

    def test_no_reply_suggestion_while_the_bot_handles_the_conversation(self):
        # Pending = the agent bot is still qualifying; a note on every Quick Reply click is noise.
        with patch.object(intel, "frappe", self.frappe):
            intel.enqueue_analysis({"message_type": "incoming", "conversation": {"id": 5, "status": "pending"}})
        self.assertEqual(self.frappe.enqueue.call_args.kwargs["suggest_reply"], False)

    def test_ignores_outgoing_and_private_messages(self):
        with patch.object(intel, "frappe", self.frappe):
            self.assertEqual(intel.enqueue_analysis({"message_type": "outgoing", "conversation": {"id": 5}})["status"], "ignored")
            self.assertEqual(intel.enqueue_analysis({"message_type": "incoming", "private": True, "conversation": {"id": 5}})["status"], "ignored")
        self.frappe.enqueue.assert_not_called()

    def test_does_nothing_without_an_api_key(self):
        self.frappe.conf = {}
        with patch.object(intel, "frappe", self.frappe):
            self.assertEqual(intel.enqueue_analysis({"message_type": "incoming", "conversation": {"id": 5}})["reason"], "ai_disabled")
        self.frappe.enqueue.assert_not_called()


class TestAnalyzeConversation(unittest.TestCase):
    def setUp(self):
        self.frappe = MagicMock()
        self.frappe.conf = {"typesafe_api_key": "jev-key", "chatwoot_api_token": "cw"}
        self.frappe.db.exists.return_value = True
        self.frappe.db.get_value.return_value = {"mobile_no": "", "email": ""}
        self.frappe.get_all.return_value = []
        self.client = MagicMock()
        self.client.list_messages.return_value = conversation({"crm_lead_id": "LEAD-1"})

    def run_job(self, answers, sleep=None, suggest_reply=True):
        with patch.object(intel, "frappe", self.frappe), \
                patch.object(intel, "_chatwoot_client", return_value=self.client), \
                patch.object(intel, "ask_jev", return_value=answers) as ask, \
                patch.object(intel, "compute_data_quality") as dq:
            result = intel.analyze_conversation(5, suggest_reply=suggest_reply, sleep=sleep or MagicMock())
        return result, ask, dq

    def test_without_suggest_reply_it_still_classifies_but_posts_no_note(self):
        result, ask, _ = self.run_job(CONFIDENT, suggest_reply=False)
        self.assertNotIn("reply", ask.call_args[0][2])
        self.assertEqual(result["applied"], ["lead_updated", "labels_added"])
        self.client.send_private_note.assert_not_called()

    def test_does_not_repeat_the_same_suggestion_as_the_last_note(self):
        convo = conversation({"crm_lead_id": "LEAD-1"})
        note = intel.decide_actions(CONFIDENT, DEFAULT_REPLY_TEMPLATES, 0.7, {"mobile_no": "", "email": ""})["reply_note"]
        convo["payload"].append({"message_type": 1, "private": True, "content": note})
        self.client.list_messages.return_value = convo
        answers = {**CONFIDENT, "reply": {"choice": "send_price", "confidence": 0.85}}
        result, _, _ = self.run_job(answers)
        self.assertNotIn("reply_suggested", result["applied"])
        self.client.send_private_note.assert_not_called()

    def test_sends_only_the_chat_to_jev_and_applies_confident_decisions(self):
        result, ask, dq = self.run_job(CONFIDENT)
        self.assertEqual(result["applied"], ["lead_updated", "labels_added", "reply_suggested"])

        api_key, state, questions = ask.call_args[0]
        self.assertEqual(api_key, "jev-key")
        self.assertEqual(ask.call_args[1]["url"], intel.JEV_URL)
        self.assertEqual([m["from"] for m in state["chat"]], ["customer", "business", "customer"], "private notes and activity are not sent")
        self.assertEqual(list(questions["phone"]["criteria"]), ["+84901234567", "none"])
        self.assertEqual(set(questions["reply"]["criteria"]) - {"none"}, set(DEFAULT_REPLY_TEMPLATES))

        self.frappe.db.set_value.assert_called_once_with("CRM Lead", "LEAD-1", {"ai_intent": "price_inquiry", "ai_hotness": "hot", "mobile_no": "+84901234567"})
        dq.assert_called_once_with("LEAD-1")
        self.client.add_labels.assert_called_once_with(5, ["ai-price_inquiry", "hot"])
        self.assertIn("bảng giá", self.client.send_private_note.call_args[0][1])

    def test_jev_url_can_point_at_a_proxy(self):
        self.frappe.conf["typesafe_api_url"] = "http://proxy.local/v1/systemone"
        _, ask, _ = self.run_job(CONFIDENT)
        self.assertEqual(ask.call_args[1]["url"], "http://proxy.local/v1/systemone")

    def test_flags_never_merges_another_lead_with_the_newly_found_phone(self):
        self.frappe.get_all.return_value = ["LEAD-ADS-7"]
        result, _, dq = self.run_job({**CONFIDENT, "reply": {"choice": "none", "confidence": 0.9}})
        self.assertEqual(result["applied"], ["lead_updated", "duplicate_flagged", "labels_added"])
        self.assertEqual(self.frappe.get_all.call_args[1]["or_filters"], [["mobile_no", "=", "+84901234567"]])
        note = self.frappe.get_doc.call_args[0][0]
        self.assertEqual(note["reference_docname"], "LEAD-1")
        self.assertIn("LEAD-ADS-7", note["content"])
        dq.assert_called_once_with("LEAD-1")

    def test_waits_for_the_lead_created_by_the_racing_conversation_webhook(self):
        # First look: contact not linked yet; after one wait the sync webhook has linked it.
        self.client.list_messages.side_effect = [conversation({}), conversation({"crm_lead_id": "LEAD-1"})]
        self.frappe.db.get_value.side_effect = [None, {"mobile_no": "", "email": ""}]
        sleep = MagicMock()
        result, _, _ = self.run_job(CONFIDENT, sleep=sleep)
        sleep.assert_called_once_with(4)
        self.assertEqual(result["lead_id"], "LEAD-1")

    def test_gives_up_without_calling_jev_when_no_lead_ever_appears(self):
        self.client.list_messages.return_value = conversation({})
        self.frappe.db.get_value.return_value = None
        sleep = MagicMock()
        result, ask, _ = self.run_job(CONFIDENT, sleep=sleep)
        self.assertEqual(result, {"status": "no_lead"})
        self.assertEqual([c[0][0] for c in sleep.call_args_list], [4, 8, 16])
        ask.assert_not_called()


if __name__ == "__main__":
    unittest.main()
