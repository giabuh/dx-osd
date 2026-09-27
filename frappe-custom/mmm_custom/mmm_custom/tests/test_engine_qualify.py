import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeJev, FakeRepo, demo_catalog, fill, render

from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.pipeline import parse_event, run_turn
from mmm_custom.engine.qualify import NEW, QUALIFIED, UNQUALIFIED, lead_status
from mmm_custom.engine.state import ConversationState

CAT = demo_catalog()
PHONE = fill("+84901234567")


def incoming(text, message_id=5):
    return {"event": "message_created", "id": message_id, "content": text, "message_type": "incoming",
            "private": False, "sender": {"id": 9, "name": "Lan", "type": "contact"},
            "conversation": {"id": 7, "inbox_id": 3, "meta": {"sender": {"id": 9, "name": "Lan", "custom_attributes": {}}}}}


class TestLeadStatus(unittest.TestCase):
    def test_course_and_phone_make_a_qualified_lead(self):
        self.assertEqual(lead_status({"course": fill("VP-EXCEL"), "phone": PHONE}, {}, CAT), QUALIFIED)

    def test_course_alone_is_still_new(self):
        self.assertEqual(lead_status({"course": fill("VP-EXCEL")}, {}, CAT), NEW)

    def test_hot_customer_is_qualified(self):
        self.assertEqual(lead_status({}, {"ai_hotness": "hot"}, CAT), QUALIFIED)

    def test_a_purchase_intent_alone_is_not_enough(self):
        # Jev reads "chưa biết gì thì học được không" as purchase: too noisy to qualify on (live check 2026-09-27)
        self.assertEqual(lead_status({}, {"ai_intent": "purchase"}, CAT), NEW)

    def test_existing_student_or_spam_is_unqualified(self):
        self.assertEqual(lead_status({}, {"ai_intent": "support"}, CAT), UNQUALIFIED)
        self.assertEqual(lead_status({}, {"ai_intent": "spam"}, CAT), UNQUALIFIED)

    def test_contact_details_beat_a_support_intent(self):
        slots = {"course": fill("VP-EXCEL"), "phone": PHONE}
        self.assertEqual(lead_status(slots, {"ai_intent": "support"}, CAT), QUALIFIED)

    def test_a_qualified_lead_is_never_downgraded_by_the_bot(self):
        self.assertEqual(lead_status({}, {"ai_intent": "support"}, CAT, QUALIFIED), QUALIFIED)
        self.assertEqual(lead_status({}, {}, CAT, QUALIFIED), QUALIFIED)

    def test_an_unqualified_lead_can_become_qualified(self):
        slots = {"course": fill("VP-EXCEL"), "phone": PHONE}
        self.assertEqual(lead_status(slots, {}, CAT, UNQUALIFIED), QUALIFIED)


class TestStatusInTheTurn(unittest.TestCase):
    def setUp(self):
        self.repo, self.fx = FakeRepo(CAT), RecordingEffects()

    def test_giving_the_phone_marks_the_lead_qualified(self):
        self.repo.states["7"] = ConversationState("7", contact_id="9", lead="CRM-LEAD-1", turns=2,
                                                  slots={"course": fill("VP-EXCEL"), "branch": fill("CN Dĩ An")},
                                                  pending={"slot": "phone"})
        turn = run_turn(parse_event(incoming("0901234567")), self.repo, self.fx, render)
        self.assertEqual(self.fx.of("save_lead")[-1]["fields"]["status"], QUALIFIED)
        self.assertEqual(self.repo.states["7"].ai["status"], QUALIFIED)
        self.assertIn("tiềm năng", turn.reason)

    def test_status_is_written_once(self):
        self.repo.jev = FakeJev({"intent": {"choice": "support", "confidence": 0.9}})
        self.repo.states["7"] = ConversationState("7", contact_id="9", lead="CRM-LEAD-1", turns=1)
        run_turn(parse_event(incoming("cho em hỏi lịch lớp em đang học")), self.repo, self.fx, render)
        run_turn(parse_event(incoming("lớp em đang học á", 6)), self.repo, self.fx, render)
        statuses = [w["fields"].get("status") for w in self.fx.of("save_lead")]
        self.assertEqual(statuses.count(UNQUALIFIED), 1)

    def test_no_lead_is_created_just_to_mark_it_unqualified(self):
        self.repo.jev = FakeJev({"intent": {"choice": "support", "confidence": 0.9}})
        run_turn(parse_event(incoming("cho em hỏi lịch lớp em đang học")), self.repo, self.fx, render)
        self.assertEqual(self.fx.of("save_lead"), [])


if __name__ == "__main__":
    unittest.main()
