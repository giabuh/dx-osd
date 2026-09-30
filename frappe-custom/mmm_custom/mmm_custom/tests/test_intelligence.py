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
    HOTNESS,
    INTENTS,
    build_questions,
    decide_actions,
    find_candidates,
)

CONFIDENT = {
    "intent": {"choice": "price_inquiry", "confidence": 0.9},
    "hotness": {"score": 2, "confidence": 0.8},
    "phone": {"choice": "+84901234567", "confidence": 0.95},
}
DRAFT = "💡 Jev gợi ý (khóa Excel từ cơ bản đến nâng cao; dựa trên: báo học phí):\n\nDạ học phí khóa Excel là 1.500.000đ ạ."
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
        bare = build_questions({"phones": [], "emails": []})
        self.assertEqual(list(bare), ["intent", "hotness"])
        full = build_questions({"phones": ["+84901234567"], "emails": ["a@b.com"]})
        self.assertEqual(list(full), ["intent", "hotness", "phone", "email"])
        self.assertEqual(list(full["phone"]["criteria"]), ["+84901234567", "none"])
        self.assertEqual(len(full["hotness"]["criteria"]), len(HOTNESS))

    def test_confident_answers_update_the_lead_and_label(self):
        plan = decide_actions(CONFIDENT, 0.7, EMPTY_LEAD)
        self.assertEqual(plan["lead_update"], {"ai_intent": "price_inquiry", "ai_hotness": "hot", "mobile_no": "+84901234567"})
        self.assertEqual(plan["labels"], ["ai-price_inquiry", "hot"])
        self.assertEqual(plan["skipped"], [])

    def test_nothing_is_applied_below_the_threshold(self):
        unsure = {k: {**v, "confidence": 0.4} for k, v in CONFIDENT.items()}
        plan = decide_actions(unsure, 0.7, EMPTY_LEAD)
        self.assertEqual(plan["lead_update"], {})
        self.assertEqual(plan["labels"], [])
        self.assertEqual(plan["skipped"], ["intent", "hotness", "phone"])

    def test_never_overwrites_a_phone_the_lead_already_has(self):
        plan = decide_actions(CONFIDENT, 0.7, {"mobile_no": "+84999999999", "email": ""})
        self.assertNotIn("mobile_no", plan["lead_update"])

    def test_spam_phone_is_never_copied(self):
        # Real Jev run: an ad for "tăng like" was spam (0.87) and its Zalo number scored 0.69 as "the customer's own".
        answers = {**CONFIDENT, "intent": {"choice": "spam", "confidence": 0.87}}
        plan = decide_actions(answers, 0.7, EMPTY_LEAD)
        self.assertEqual(plan["lead_update"]["ai_intent"], "spam")
        self.assertNotIn("mobile_no", plan["lead_update"])


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


class TestEnrolDecision(unittest.TestCase):
    ENROL = {"choice": "enrol", "confidence": 0.9}

    def plan(self, enrol, **kw):
        return decide_actions({**CONFIDENT, "enrol": enrol}, 0.7, EMPTY_LEAD, **kw)

    def test_a_sure_yes_plans_a_draft(self):
        self.assertTrue(self.plan(self.ENROL)["enrol"])

    def test_below_the_enrol_floor_or_not_yet_plans_nothing(self):
        self.assertFalse(self.plan({"choice": "enrol", "confidence": 0.8})["enrol"])
        self.assertFalse(self.plan({"choice": "not_yet", "confidence": 0.99})["enrol"])
        self.assertTrue(self.plan({"choice": "enrol", "confidence": 0.8}, enrol_floor=0.75)["enrol"])

    def test_no_answer_or_spam_plans_nothing(self):
        self.assertFalse(decide_actions(CONFIDENT, 0.7, EMPTY_LEAD)["enrol"])
        spam = {**CONFIDENT, "intent": {"choice": "spam", "confidence": 0.9}, "enrol": self.ENROL}
        self.assertFalse(decide_actions(spam, 0.7, EMPTY_LEAD)["enrol"])

    def test_the_floor_never_drops_below_the_site_threshold(self):
        answers = {**CONFIDENT, "enrol": {"choice": "enrol", "confidence": 0.8}}
        self.assertFalse(decide_actions(answers, 0.9, EMPTY_LEAD, enrol_floor=0.5)["enrol"])


class TestEnrolEligible(unittest.TestCase):
    def ok(self, **kw):
        args = dict(status="Contacted", phone=True, course="VP-EXCEL", has_live_deal=False, enabled=True)
        return intel.enrol_eligible(**{**args, **kw})

    def test_an_open_lead_with_a_course_and_a_phone_and_no_registration(self):
        self.assertTrue(self.ok())
        self.assertTrue(self.ok(status="Converted"))  # an existing student adding a course

    def test_the_question_is_only_worth_asking_when_a_draft_could_be_made(self):
        for kw in ({"status": "Unqualified"}, {"status": "Junk"}, {"status": None}, {"phone": False},
                   {"course": ""}, {"has_live_deal": True}, {"enabled": False}):
            self.assertFalse(self.ok(**kw), kw)

    def test_the_enrol_question_is_added_on_demand(self):
        self.assertNotIn("enrol", build_questions({"phones": [], "emails": []}))
        q = build_questions({"phones": [], "emails": []}, ask_enrol=True)["enrol"]
        self.assertEqual(list(q["criteria"]), ["enrol", "not_yet"])


class TestEnqueue(unittest.TestCase):
    def setUp(self):
        self.frappe = MagicMock()
        self.frappe.conf = {"typesafe_api_key": "k"}
        self.frappe.db.exists.return_value = None

    def test_skips_conversations_the_bot_is_handling(self):
        self.frappe.db.exists.return_value = "7"
        with patch.object(intel, "frappe", self.frappe):
            result = intel.enqueue_analysis({"message_type": "incoming", "conversation": {"id": 7}})
        self.assertEqual(result, {"status": "ignored", "reason": "bot_active"})
        self.frappe.enqueue.assert_not_called()
        self.frappe.db.exists.assert_called_with("Bot Conversation",
                                                 {"conversation_id": "7", "status": "active", "is_sandbox": 0})

    def test_queues_incoming_messages(self):
        conversation = {"id": 5, "status": "open", "meta": {"assignee": {"id": 3, "type": "user"}}}
        with patch.object(intel, "frappe", self.frappe):
            result = intel.enqueue_analysis({"event": "message_created", "message_type": "incoming",
                                             "conversation": conversation})
        self.assertEqual(result["status"], "queued")
        self.frappe.enqueue.assert_called_once_with("mmm_custom.intelligence.analyze_conversation", queue="long", conversation_id=5, suggest_reply=True)

    def test_no_reply_suggestion_before_a_staff_member_takes_the_conversation(self):
        # D-108: the suggestion comes when someone takes it (enqueue_on_assignment); intent/labels still run.
        with patch.object(intel, "frappe", self.frappe):
            result = intel.enqueue_analysis({"message_type": "incoming", "conversation": {"id": 5, "status": "open"}})
        self.assertEqual(result["status"], "queued")
        self.assertEqual(self.frappe.enqueue.call_args.kwargs["suggest_reply"], False)

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


def assigned(current=3, previous=None, last=None, assignee_type="user", conversation_id=9):
    return {"event": "conversation_updated", "id": conversation_id,
            "changed_attributes": [{"assignee_id": {"previous_value": previous, "current_value": current}}],
            "meta": {"assignee": {"id": current, "type": assignee_type} if current else None},
            "messages": [last if last is not None else {"message_type": 0, "sender": {"type": "contact"}}]}


class TestAssignmentTrigger(unittest.TestCase):
    def test_taken_by_a_staff_member_while_the_customer_waits(self):
        self.assertEqual(intel.assignment_trigger(assigned()), 9)
        self.assertEqual(intel.assignment_trigger(assigned(current=4, previous=3)), 9)  # passed to a colleague
        bot_spoke_last = {"message_type": 1, "sender": {"type": "agent_bot"}}
        self.assertEqual(intel.assignment_trigger(assigned(last=bot_spoke_last)), 9)  # the bot's handoff message

    def test_no_trigger(self):
        self.assertIsNone(intel.assignment_trigger(assigned(current=None, previous=3)))  # unassigned
        self.assertIsNone(intel.assignment_trigger(assigned(current=3, previous=3)))
        self.assertIsNone(intel.assignment_trigger(assigned(assignee_type="agent_bot")))
        staff_spoke_last = {"message_type": 1, "sender": {"type": "user"}}
        self.assertIsNone(intel.assignment_trigger(assigned(last=staff_spoke_last)))
        other_change = {**assigned(), "changed_attributes": [{"label_list": {"previous_value": [], "current_value": ["x"]}}]}
        self.assertIsNone(intel.assignment_trigger(other_change))
        self.assertIsNone(intel.assignment_trigger({**assigned(), "messages": []}))
        self.assertIsNone(intel.assignment_trigger({"id": 9}))

    def test_human_assignee(self):
        self.assertTrue(intel.has_human_assignee({"meta": {"assignee": {"id": 1, "type": "user"}}}))
        self.assertTrue(intel.has_human_assignee({"meta": {"assignee": {"id": 1}}}))
        self.assertFalse(intel.has_human_assignee({"meta": {"assignee": {"id": 1, "type": "agent_bot"}}}))
        self.assertFalse(intel.has_human_assignee({"meta": {"assignee": None}}))
        self.assertFalse(intel.has_human_assignee({}))


class TestEnqueueOnAssignment(unittest.TestCase):
    def setUp(self):
        self.frappe = MagicMock()
        self.frappe.conf = {"typesafe_api_key": "k"}
        self.frappe.db.exists.return_value = None

    def test_queues_one_suggestion_per_conversation(self):
        with patch.object(intel, "frappe", self.frappe):
            self.assertEqual(intel.enqueue_on_assignment(assigned())["status"], "queued")
        self.frappe.enqueue.assert_called_once_with(
            "mmm_custom.intelligence.analyze_conversation", queue="long", conversation_id=9, suggest_reply=True,
            job_id="ai_suggest_9", deduplicate=True)

    def test_skips_while_the_bot_is_talking_without_a_key_or_trigger(self):
        with patch.object(intel, "frappe", self.frappe):
            self.assertEqual(intel.enqueue_on_assignment(assigned(current=None, previous=3))["reason"], "not_assigned")
            self.frappe.db.exists.return_value = "7"
            self.assertEqual(intel.enqueue_on_assignment(assigned())["reason"], "bot_active")
            self.frappe.conf = {}
            self.assertEqual(intel.enqueue_on_assignment(assigned())["reason"], "ai_disabled")
        self.frappe.enqueue.assert_not_called()


class TestOnHandedOff(unittest.TestCase):
    def setUp(self):
        self.frappe = MagicMock()
        self.frappe.conf = {"typesafe_api_key": "k"}

    def test_queues_after_the_turn_commits(self):
        with patch.object(intel, "frappe", self.frappe):
            intel.on_handed_off({"event": "handed_off", "conversation_id": "12", "is_sandbox": False})
        self.frappe.enqueue.assert_called_once_with(
            "mmm_custom.intelligence.analyze_conversation", queue="long", conversation_id=12, suggest_reply=True,
            job_id="ai_suggest_12", deduplicate=True, enqueue_after_commit=True)

    def test_skips_playground_and_sites_without_a_key(self):
        with patch.object(intel, "frappe", self.frappe):
            intel.on_handed_off({"conversation_id": "12", "is_sandbox": True})
            self.frappe.conf = {}
            intel.on_handed_off({"conversation_id": "12", "is_sandbox": False})
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

    def run_job(self, answers, sleep=None, suggest_reply=True, draft=DRAFT):
        with patch.object(intel, "frappe", self.frappe), \
                patch.object(intel, "_chatwoot_client", return_value=self.client), \
                patch.object(intel, "ask_jev", return_value=answers) as ask, \
                patch.object(intel, "draft_note", return_value=draft) as self.draft, \
                patch.object(intel, "compute_data_quality") as dq:
            result = intel.analyze_conversation(5, suggest_reply=suggest_reply, sleep=sleep or MagicMock())
        return result, ask, dq

    def test_without_suggest_reply_it_still_classifies_but_posts_no_note(self):
        result, ask, _ = self.run_job(CONFIDENT, suggest_reply=False)
        self.draft.assert_not_called()
        self.assertEqual(result["applied"], ["lead_updated", "labels_added"])
        self.client.send_private_note.assert_not_called()

    def test_does_not_repeat_the_same_suggestion_as_the_last_note(self):
        convo = conversation({"crm_lead_id": "LEAD-1"})
        convo["payload"].append({"message_type": 1, "private": True, "content": DRAFT})
        self.client.list_messages.return_value = convo
        result, _, _ = self.run_job(CONFIDENT)
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
        self.assertNotIn("reply", questions, "the suggestion is the bot's own draft, not a template Jev picks")

        self.frappe.db.set_value.assert_called_once_with("CRM Lead", "LEAD-1", {"ai_intent": "price_inquiry", "ai_hotness": "hot", "mobile_no": "+84901234567"})
        dq.assert_called_once_with("LEAD-1")
        self.client.add_labels.assert_called_once_with(5, ["ai-price_inquiry", "hot"])
        self.assertEqual(self.client.send_private_note.call_args[0][1], DRAFT)
        self.assertEqual(self.draft.call_args[0][0], 5)

    def eligible_lead(self):
        def get_value(doctype, filters, fieldname=None, **kw):
            if doctype == "CRM Products":
                return "VP-EXCEL"
            return {"mobile_no": "0901234567", "email": "", "status": "Contacted"}
        self.frappe.db.get_value.side_effect = get_value
        self.frappe.db.exists.side_effect = lambda doctype, *a: doctype == "CRM Lead"  # no live registration

    def test_a_sure_yes_drafts_a_registration_and_tells_the_consultant(self):
        self.eligible_lead()
        answers = {**CONFIDENT, "enrol": {"choice": "enrol", "confidence": 0.95}}
        with patch("mmm_custom.enrolment.create_draft", return_value="CRM-DEAL-1") as draft:
            result, ask, _ = self.run_job(answers, draft=None)
        self.assertIn("enrol", ask.call_args[0][2])
        draft.assert_called_once_with("LEAD-1", "VP-EXCEL", source="jev")
        self.assertIn("draft_registration", result["applied"])
        self.assertIn("CRM-DEAL-1", self.client.send_private_note.call_args[0][1])

    def test_an_ineligible_lead_is_not_even_asked(self):
        result, ask, _ = self.run_job(CONFIDENT, draft=None)
        self.assertNotIn("enrol", ask.call_args[0][2])
        self.assertNotIn("draft_registration", result["applied"])

    def test_a_failing_draft_never_breaks_the_analysis(self):
        self.eligible_lead()
        answers = {**CONFIDENT, "enrol": {"choice": "enrol", "confidence": 0.95}}
        with patch("mmm_custom.enrolment.create_draft", side_effect=RuntimeError("db")):
            result, _, _ = self.run_job(answers, draft=None)
        self.assertEqual(result["status"], "analyzed")
        self.assertNotIn("draft_registration", result["applied"])

    def test_jev_url_can_point_at_a_proxy(self):
        self.frappe.conf["typesafe_api_url"] = "http://proxy.local/v1/systemone"
        _, ask, _ = self.run_job(CONFIDENT)
        self.assertEqual(ask.call_args[1]["url"], "http://proxy.local/v1/systemone")

    def test_flags_never_merges_another_lead_with_the_newly_found_phone(self):
        self.frappe.get_all.return_value = ["LEAD-ADS-7"]
        result, _, dq = self.run_job(CONFIDENT, draft=None)
        self.assertEqual(result["applied"], ["lead_updated", "duplicate_flagged", "labels_added"])
        self.assertEqual(self.frappe.get_all.call_args[1]["or_filters"], [["mobile_no", "=", "+84901234567"]])
        note = self.frappe.get_doc.call_args[0][0]
        self.assertEqual(note["reference_docname"], "LEAD-1")
        self.assertIn("LEAD-ADS-7", note["content"])
        dq.assert_called_once_with("LEAD-1")

    def test_waits_for_the_lead_created_by_the_racing_conversation_webhook(self):
        # First look: contact not linked yet; after one wait the sync webhook has linked it.
        self.client.list_messages.side_effect = [conversation({}), conversation({"crm_lead_id": "LEAD-1"})]
        self.frappe.db.get_value.side_effect = [None, {"mobile_no": "", "email": ""}, None]  # lead lookup, lead, course
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
