import json
import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeRepo, demo_catalog, fill, render

from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.learning import corrections
from mmm_custom.engine.log import log_row, signals
from mmm_custom.engine.pipeline import Event, run_turn
from mmm_custom.engine.state import ConversationState
from mmm_custom.engine.understand import Understanding

CAT = demo_catalog()


def event(text="alo", message_id=5):
    return Event("customer_message", "7", message_id, text, {"id": 9})


class TestLogRow(unittest.TestCase):
    def setUp(self):
        self.repo = FakeRepo(CAT)

    def test_one_row_per_processed_message_none_on_redelivery(self):
        run_turn(event(), self.repo, RecordingEffects(), render)
        run_turn(event(), self.repo, RecordingEffects(), render)
        self.assertEqual(len(self.repo.logs), 1)
        row = self.repo.logs[0]
        self.assertEqual((row["decision_type"], row["asked_slot"], row["jev_status"], row["message_id"]),
                         ("ask_slot", "course", "disabled", "5"))
        self.assertEqual(len(json.loads(row["reply_buttons"])), 9)
        self.assertEqual((json.loads(row["slots_before"]), row["status_before"], row["turns_before"]), ({}, "active", 0))
        self.assertIn("Trợ lý Sao Việt", row["reply_text"])
        self.assertEqual(json.loads(row["errors"]), [])

    def test_stuck_handoff_emits_stuck_and_unmatched_terms(self):
        self.repo.states["7"] = ConversationState("7", turns=3, stuck_turns=1)
        run_turn(event("abcxyz qwerty", 9), self.repo, RecordingEffects(), render)
        types = [(s["signal_type"], s.get("term")) for s in self.repo.signals]
        self.assertEqual(types, [("stuck", None), ("unmatched_term", "abcxyz"), ("unmatched_term", "qwerty")])

    def test_log_failure_never_raises(self):
        self.repo.write_log = MagicMock(side_effect=RuntimeError("db"))
        t = run_turn(event(), self.repo, RecordingEffects(), render)
        self.assertEqual(t.reply.errors[-1]["type"], "log_failed")


class TestSignalsPure(unittest.TestCase):
    def test_render_error_signal(self):
        from mmm_custom.engine.decide import Decision
        from mmm_custom.engine.pipeline import Turn
        from mmm_custom.engine.reply import Reply
        reply = Reply(errors=[{"type": "render_error", "source": "duration", "detail": "x"}])
        turn = Turn(event(), ConversationState("7"), Understanding(), Decision("answer"), reply)
        self.assertEqual([s["signal_type"] for s in signals(turn)], ["render_error"])
        self.assertEqual(log_row(turn)["decision_type"], "answer")


class TestCorrections(unittest.TestCase):
    def test_person_changes_branch_or_course_the_bot_set(self):
        bot = {"branch": fill("CN Dĩ An"), "course": fill("VP-EXCEL")}
        before = {"territory": "CN Dĩ An", "products": ["VP-EXCEL"]}
        after = {"territory": "CN Thuận An", "products": ["VP-WORD"]}
        self.assertEqual(corrections(before, after, bot, CAT), [
            {"field": "territory", "bot_value": "CN Dĩ An", "new_value": "CN Thuận An"},
            {"field": "products", "bot_value": "VP-EXCEL", "new_value": "VP-WORD"}])

    def test_no_signal_for_values_from_the_lead_or_unchanged(self):
        bot = {"branch": {"value": "CN Dĩ An", "source": "lead"}}
        self.assertEqual(corrections({"territory": "CN Dĩ An", "products": []},
                                     {"territory": "CN Thuận An", "products": []}, bot, CAT), [])
        bot = {"branch": fill("CN Dĩ An")}
        same = {"territory": "CN Dĩ An", "products": []}
        self.assertEqual(corrections(same, same, bot, CAT), [])


if __name__ == "__main__":
    unittest.main()
