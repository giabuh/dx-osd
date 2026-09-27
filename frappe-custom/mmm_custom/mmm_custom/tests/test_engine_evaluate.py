import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import demo_catalog

from mmm_custom.engine.evaluate import evaluate_items, expected_answers, grade, item_state, load_utterances, summarize
from mmm_custom.engine.jev_questions import NONE, build_questions
from mmm_custom.engine.understand import understand

CAT = demo_catalog()
ITEMS = load_utterances()


def perfect(item_by_text, wrong=None):
    """A fake Jev that answers every question as labelled, except `wrong` = {question: answer}."""
    def ask(state, questions):
        item = item_by_text[state["latest_message"]]
        exp = expected_answers(item, questions, CAT)
        out = {}
        for key, q in questions.items():
            want = exp.get(key, NONE if q["type"] == "choice" else False)
            if q["type"] == "noul":
                out[key] = {"noul": 0.97 if want else 0.02}
            elif q["type"] == "score":
                out[key] = {"score": 1.0, "confidence": 0.9}
            else:
                out[key] = {"choice": want, "confidence": 0.97}
        out.update(wrong or {})
        return out
    return ask


class TestUtterances(unittest.TestCase):
    def test_at_least_100_unique_and_all_labels_exist_in_the_catalog(self):
        self.assertGreaterEqual(len(ITEMS), 100)
        self.assertEqual(len({i["id"] for i in ITEMS}), len(ITEMS))
        for item in ITEMS:
            exp = item["expect"]
            for key, value in exp.get("slots", {}).items():
                slot = CAT.slot(key)
                self.assertIsNotNone(slot, item["id"])
                if slot.type == "catalog":
                    self.assertIn(value, CAT.courses if slot.source == "course" else CAT.branches, item["id"])
                elif slot.type == "choice":
                    self.assertIsNotNone(slot.option(value), item["id"])
            for key, value in exp.get("parents", {}).items():
                self.assertIn(value, CAT.groups if key == "course" else CAT.areas, item["id"])
            for skill in exp.get("skills", []):
                self.assertIn(skill, CAT.skills, item["id"])
            if item.get("pending"):
                self.assertIsNotNone(CAT.slot(item["pending"]), item["id"])

    def test_hard_categories_are_covered(self):
        tags = {t for i in ITEMS for t in i["tags"]}
        self.assertTrue({"no_diacritics", "abbreviation", "multi_slot", "multi_topic", "negation", "spam", "b2b",
                         "short_answer", "wants_human"} <= tags)


class TestGrading(unittest.TestCase):
    def test_expected_answers(self):
        item = {"id": "x", "text": "robot cho con 8 tuoi o di an", "pending": None,
                "expect": {"slots": {"course": "TE-ROBO", "branch": "CN Dĩ An", "learner": "child"}, "skills": ["fee_quote"]}}
        state = item_state(item)
        q = build_questions(state, understand(item["text"], state, CAT), CAT)
        exp = expected_answers(item, q, CAT)
        self.assertEqual((exp["slot:course"], exp["slot:branch"]), ("TE-ROBO", "CN Dĩ An"))
        self.assertEqual((exp["slot:preferred_shift"], exp["skill:fee_quote"], exp["skill:hotline"], exp["wants_human"]),
                         (NONE, True, False, False))
        self.assertNotIn("intent", exp)
        item["expect"]["skip"] = ["skill:hotline"]
        self.assertNotIn("skill:hotline", expected_answers(item, q, CAT))

    def test_grade_bands(self):
        self.assertTrue(grade("skill:hotline", {"noul": 0.9}, False, CAT)["act_wrong"])
        self.assertEqual(grade("skill:hotline", {"noul": 0.7}, False, CAT)["band"], "confirm")
        self.assertEqual(grade("slot:course", {"choice": NONE, "confidence": 0.99}, "VP-EXCEL", CAT)["band"], "low")
        row = grade("slot:course", {"choice": "VP-EXCEL", "confidence": 0.9}, "VP-EXCEL", CAT)
        self.assertEqual((row["band"], row["correct"], row["act_wrong"]), ("act", True, False))
        self.assertEqual(grade("intent", {"choice": "price_inquiry", "confidence": 0.99}, "spam", CAT)["band"], "low")

    def test_gate_passes_only_without_critical_act_errors(self):
        items = ITEMS[:12]
        by_text = {i["text"]: i for i in items}
        report = summarize(evaluate_items(items, CAT, perfect(by_text)))
        self.assertTrue(report["passed"])
        self.assertEqual(report["critical_act_wrong"], 0)
        bad = summarize(evaluate_items(items, CAT, perfect(by_text, {"skill:hotline": {"noul": 0.95}})))
        self.assertFalse(bad["passed"])
        self.assertGreater(bad["critical_act_wrong"], 0)

    def test_failed_calls_fail_the_gate(self):
        report = summarize(evaluate_items(ITEMS[:2], CAT, lambda state, questions: None))
        self.assertEqual((report["errors"], report["passed"]), (2, False))


if __name__ == "__main__":
    unittest.main()
