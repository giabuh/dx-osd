import contextlib
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeRepo, demo_catalog, demo_consultants, fill, render

from mmm_custom import quiz_reminders
from mmm_custom.engine import offers
from mmm_custom.engine.decide import Decision
from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.pipeline import parse_event, run_turn
from mmm_custom.engine.state import ConversationState

CAT = demo_catalog()
NOW = datetime(2026, 9, 28, 12, 0)


def quiz_state(progress="excel_quiz:0,1,0", status=offers.STARTED):
    return ConversationState("7", slots={"course": fill("VP-EXCEL"), "quiz_progress": fill(progress)},
                             offers={"excel_quiz": status})


class TestDue(unittest.TestCase):
    def test_window(self):
        for hours, expected in ((1, False), (2, True), (19.5, True), (20, False), (30, False)):
            self.assertEqual(quiz_reminders.due(NOW - timedelta(hours=hours), NOW, 2), expected, hours)


class TestReminderReply(unittest.TestCase):
    def test_left_questions_and_the_buttons_of_the_current_one(self):
        reply = quiz_reminders.reminder_reply(quiz_state(), "excel_quiz", CAT, render)
        self.assertEqual(reply.messages, ["Dạ anh/chị ơi, bài test Excel chỉ còn 2 câu nữa là xong rồi ạ, anh/chị làm tiếp "
                                          "để nhận quà nhé 🎁\nCâu 4/5: Hàm nào đếm số ô thỏa một điều kiện?"])
        self.assertEqual([b["title"] for b in reply.buttons], ["COUNTIF", "SUMIF", "IF", "LEN"])
        self.assertEqual(reply.options()["COUNTIF"]["value"], "excel_quiz:0,1,0,0")

    def test_nothing_to_remind(self):
        self.assertIsNone(quiz_reminders.reminder_reply(quiz_state("excel_quiz:0,1,0,0,0"), "excel_quiz", CAT, render))
        self.assertIsNone(quiz_reminders.reminder_reply(quiz_state(), "fee_quote", CAT, render))


class TestAttempts(unittest.TestCase):
    def test_changes(self):
        self.assertEqual(offers.attempt_changes({}, {"excel_quiz": "offered"}, Decision("ask_slot"), CAT),
                         [{"quiz": "excel_quiz", "status": "offered", "offered_at": True}])
        self.assertEqual(offers.attempt_changes({"excel_quiz": "offered"}, {"excel_quiz": "declined"}, Decision("answer"), CAT),
                         [{"quiz": "excel_quiz", "status": "declined"}])
        self.assertEqual(offers.attempt_changes({"excel_quiz": "started"}, {"excel_quiz": "reminded"}, Decision("answer"), CAT), [])
        done = Decision("answer", slots={"quiz_progress": fill("excel_quiz:3,3")}, voucher={"quiz": "excel_quiz", "code": "SV-X"})
        self.assertEqual(offers.attempt_changes({"excel_quiz": "reminded"}, {"excel_quiz": "rewarded"}, done, CAT),
                         [{"quiz": "excel_quiz", "status": "done", "finished_at": True, "score": 0, "total": 2,
                           "level": "beginner", "missed": "Hàm SUM, Địa chỉ tuyệt đối", "phone_after": 1,
                           "voucher_code": "SV-X"}])

    def test_a_whole_conversation_leaves_one_attempt_row(self):
        repo, fx = FakeRepo(CAT), RecordingEffects()
        repo.consultant_rows = demo_consultants()
        for i, text in enumerate(["học excel ở dĩ an", "em tự học", "Làm bài test", "SUM", "$A$1", "Dò tìm theo mã",
                                  "COUNTIF", "Lọc thủ công", "0901234567"]):
            run_turn(parse_event({"event": "message_created", "id": 10 + i, "content": text, "message_type": "incoming",
                                  "private": False, "sender": {"id": 9, "type": "contact"},
                                  "conversation": {"id": 7, "inbox_id": 3, "meta": {"sender": {"id": 9}}}}),
                     repo, fx, render)
        self.assertEqual(list(repo.attempts), [("7", "excel_quiz")])
        row = repo.attempts[("7", "excel_quiz")]
        self.assertEqual((row["status"], row["score"], row["total"], row["level"], row["missed"], row["phone_after"]),
                         ("done", 4, 5, "basic", "Pivot Table", 1))
        self.assertTrue(row["offered_at"] and row["started_at"] and row["finished_at"])


class TestRun(unittest.TestCase):
    def run_job(self, conv, state):
        frappe = MagicMock()
        frappe.get_all.return_value = [SimpleNamespace(name="QA-1", conversation="7", quiz="excel_quiz")]
        frappe.db.get_value.return_value = conv
        repo = FakeRepo(CAT)
        repo.states["7"] = state
        effects = RecordingEffects()
        utils = ModuleType("frappe.utils")
        utils.now_datetime = lambda: NOW
        sync = ModuleType("frappe.utils.synchronization")
        sync.filelock = lambda *a, **kw: contextlib.nullcontext()
        modules = {"frappe": frappe, "frappe.utils": utils, "frappe.utils.synchronization": sync}
        with patch.dict(sys.modules, modules), patch.object(quiz_reminders, "frappe", frappe), \
                patch("mmm_custom.engine.repo.FrappeRepo", return_value=repo), \
                patch("mmm_custom.engine.effects.chatwoot_effects", return_value=effects), \
                patch("mmm_custom.engine.render.frappe_renderer", render):
            quiz_reminders.run()
        return frappe, repo, effects

    def test_quiet_customer_is_reminded_once(self):
        conv = SimpleNamespace(status="active", consultant_replied=0, modified=NOW - timedelta(hours=3))
        frappe, repo, effects = self.run_job(conv, quiz_state())
        self.assertEqual(effects.of("send")[0]["buttons"], ["COUNTIF", "SUMIF", "IF", "LEN"])
        saved = repo.states["7"]
        self.assertEqual(saved.offers, {"excel_quiz": "reminded"})
        self.assertIn("COUNTIF", saved.pending["options"])
        frappe.db.set_value.assert_called_once_with("Quiz Attempt", "QA-1", "reminded_at", NOW)

    def test_skipped(self):
        cases = {
            "too soon": (SimpleNamespace(status="active", consultant_replied=0, modified=NOW - timedelta(hours=1)), quiz_state()),
            "consultant wrote": (SimpleNamespace(status="active", consultant_replied=1, modified=NOW - timedelta(hours=3)), quiz_state()),
            "handed off": (SimpleNamespace(status="handed_off", consultant_replied=0, modified=NOW - timedelta(hours=3)), quiz_state()),
            "already reminded": (SimpleNamespace(status="active", consultant_replied=0, modified=NOW - timedelta(hours=3)),
                                 quiz_state(status=offers.REMINDED)),
        }
        for why, (conv, state) in cases.items():
            frappe, _, effects = self.run_job(conv, state)
            self.assertEqual(effects.of("send"), [], why)
            frappe.db.set_value.assert_not_called()


if __name__ == "__main__":
    unittest.main()
