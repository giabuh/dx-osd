import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import demo_catalog, promo, render

from mmm_custom import comment_funnel as cf
from mmm_custom.engine.tone import problems

CAT = demo_catalog()
NOW = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
PAGE = "1334466483083776"


def comment(text, cid="c1", name="Lan Anh", sender="u1", age=timedelta(hours=1)):
    return {"id": cid, "message": text, "from": {"id": sender, "name": name},
            "created_time": (NOW - age).strftime("%Y-%m-%dT%H:%M:%S+0000")}


class FakeSender:
    def __init__(self, psid="psid-9", fail=""):
        self.sent, self.psid, self.fail = [], psid, fail

    def public(self, comment_id, text):
        if self.fail == "public":
            raise RuntimeError("public refused")
        self.sent.append(("public", comment_id, text))

    def private(self, comment_id, text):
        if self.fail == "private":
            raise RuntimeError("(#10900) already replied")
        self.sent.append(("private", comment_id, text))
        return self.psid


def ctx(course="DH-PTS", promotions=()):
    return cf.post_context({"name": 33, "title": "Khóa photoshop", "course": course}, CAT, list(promotions), render)


class TestClassify(unittest.TestCase):
    def test_intents(self):
        quiz = ("test photoshop", "kiem tra photoshop")
        cases = {
            "Cho em làm bài test photoshop với": "quiz",
            "test": "quiz",
            "Kiểm tra trình độ được không ad": "quiz",
            "Học phí bao nhiêu vậy ạ": "price",
            "khi nào khai giảng?": "price",
            "Tư vấn giúp mình với": "interest",
            "ib em nhé": "interest",
            "Hay quá": "praise",
            "đẹp xịn": "praise",
            "Nguyễn Văn A": "other",
            "😍😍": "other",
            "": "other",
        }
        for text, intent in cases.items():
            self.assertEqual(cf.classify(text, quiz), intent, text)

    def test_a_question_beats_praise(self):
        self.assertEqual(cf.classify("hay quá, học phí sao ạ"), "price")

    def test_sentiment_labels_match_the_comment_table(self):
        self.assertEqual(cf.sentiment("price"), "Hỏi học phí / lịch")
        self.assertEqual(cf.sentiment("quiz"), "Quan tâm khóa học")
        self.assertEqual(cf.sentiment("praise"), "Tích cực")
        self.assertEqual(cf.sentiment("other"), "Spam / Khác")


class TestPlan(unittest.TestCase):
    def test_actions_per_intent(self):
        self.assertEqual(cf.plan("price"), (True, True))
        self.assertEqual(cf.plan("quiz"), (True, True))
        self.assertEqual(cf.plan("interest"), (True, True))
        self.assertEqual(cf.plan("praise"), (True, False))
        self.assertEqual(cf.plan("other"), (False, False))


class TestMessages(unittest.TestCase):
    def test_context_takes_course_quiz_and_best_promotion(self):
        c = ctx(promotions=[promo("Đồ họa -10%", groups=["Thiết kế đồ họa"]), promo("Khác", courses=["KT-TH"])])
        self.assertEqual(c.course["code"], "DH-PTS")
        self.assertEqual(c.quiz_keyword, "test photoshop")
        self.assertEqual(c.promo["title"], "Đồ họa -10%")
        self.assertEqual(c.promo["final_fee"], c.course["fee"] * 0.9)

    def test_post_without_a_known_course(self):
        c = cf.post_context({"name": 1, "title": "Chào tuần mới", "course": ""}, CAT, [], render)
        self.assertEqual((c.course, c.quiz_keyword, c.promo), ({}, "", {}))
        texts = cf.compose("interest", "Lan", c)
        self.assertNotIn("khóa", texts["private"])

    def test_price_answer_names_fee_promotion_and_test(self):
        c = ctx(promotions=[promo("Đồ họa -10%", groups=["Thiết kế đồ họa"])])
        private = cf.compose("price", "Lan Anh", c)["private"]
        self.assertIn("Lan Anh", private)
        self.assertIn(c.course["name"], private)
        self.assertIn("Đồ họa -10%", private)
        self.assertIn("test photoshop", private)
        self.assertIn("trả lời tin nhắn này", private)

    def test_no_promotion_no_offer(self):
        private = cf.compose("price", "Lan", ctx())["private"]
        self.assertNotIn("ưu đãi", private)
        self.assertNotIn("%", private)

    def test_texts_follow_the_house_tone(self):
        c = ctx(promotions=[promo("Đồ họa -10%")])
        for intent in ("quiz", "price", "interest", "praise"):
            for kind, text in cf.compose(intent, "Lan", c).items():
                if text:
                    self.assertEqual(problems(text), [], f"{intent}/{kind}: {text}")
        for kind, text in cf.compose("price", "", cf.post_context({"course": ""}, CAT, [], render)).items():
            self.assertEqual(problems(text), [], f"no name/{kind}: {text}")

    def test_praise_gets_thanks_only(self):
        texts = cf.compose("praise", "Lan", ctx())
        self.assertTrue(texts["public"])
        self.assertEqual(texts["private"], "")
        self.assertEqual(cf.compose("other", "Lan", ctx()), {"public": "", "private": ""})


class TestHandle(unittest.TestCase):
    def test_question_gets_both_replies_and_keeps_the_psid(self):
        sender = FakeSender()
        row = cf.handle(comment("học phí bao nhiêu ạ"), 33, ctx(), sender, PAGE, NOW)
        self.assertEqual([s[0] for s in sender.sent], ["public", "private"])
        self.assertEqual((row["intent"], row["status"], row["psid"]), ("price", "Replied", "psid-9"))
        self.assertEqual(row["facebook_post"], 33)
        self.assertEqual(row["comment_time"], "2026-10-01 08:00:00")
        self.assertTrue(row["public_reply"] and row["private_reply"])

    def test_spam_is_skipped(self):
        sender = FakeSender()
        row = cf.handle(comment("Nguyễn Văn B"), 33, ctx(), sender, PAGE, NOW)
        self.assertEqual((row["status"], sender.sent), ("Skipped", []))

    def test_page_own_comment_is_skipped(self):
        sender = FakeSender()
        row = cf.handle(comment("học phí?", sender=PAGE), 33, ctx(), sender, PAGE, NOW)
        self.assertEqual((row["status"], sender.sent), ("Skipped", []))

    def test_no_private_reply_after_seven_days(self):
        sender = FakeSender()
        row = cf.handle(comment("tư vấn em", age=timedelta(days=8)), 33, ctx(), sender, PAGE, NOW)
        self.assertEqual([s[0] for s in sender.sent], ["public"])
        self.assertEqual((row["status"], row["private_reply"], row["psid"]), ("Replied", "", ""))

    def test_failure_is_recorded_not_raised(self):
        row = cf.handle(comment("tư vấn em"), 33, ctx(), FakeSender(fail="private"), PAGE, NOW)
        self.assertEqual(row["status"], "Failed")
        self.assertIn("10900", row["error"])
        self.assertTrue(row["public_reply"])


class TestAttribution(unittest.TestCase):
    def test_psid_comes_from_a_facebook_contact_inbox(self):
        conv = {"channel": "Channel::FacebookPage", "contact_inbox": {"source_id": "psid-9"}}
        self.assertEqual(cf.psid_of(conv), "psid-9")
        self.assertEqual(cf.psid_of({**conv, "channel": "Channel::WebWidget"}), "")
        self.assertEqual(cf.psid_of({**conv, "additional_attributes": {"type": "instagram_direct_message"}}), "")
        self.assertEqual(cf.psid_of({"channel": "Channel::FacebookPage"}), "")
        self.assertEqual(cf.psid_of(None), "")

    def test_lead_updates_are_first_touch(self):
        self.assertEqual(cf.lead_updates({"facebook_post": None, "source_campaign": ""}, 33, "Khóa photoshop"),
                         {"facebook_post": 33, "source_campaign": "Bình luận: Khóa photoshop"})
        self.assertEqual(cf.lead_updates({"facebook_post": 30, "source_campaign": "x"}, 33, "Khóa photoshop"), {})
        self.assertEqual(cf.lead_updates({"source_campaign": ""}, 33, "y" * 200)["source_campaign"],
                         ("Bình luận: " + "y" * 200)[:140])


if __name__ == "__main__":
    unittest.main()
