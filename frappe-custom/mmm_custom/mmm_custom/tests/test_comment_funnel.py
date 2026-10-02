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
            "hi": "greeting",
            "chào shop ạ": "greeting",
            "chào shop, học phí bao nhiêu": "price",
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
        self.assertEqual(cf.plan("greeting"), (True, False))  # a hello back, never a private message
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
        for intent in ("quiz", "price", "interest", "praise", "greeting"):
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


class TestGeminiWriter(unittest.TestCase):
    """Gemini writes the replies (D-129); anything it writes is checked, and a failed check falls back to the template."""

    def ctx_with(self, answer):
        from mmm_custom.marketing_plan import build_facts

        c = ctx(promotions=[promo("Đồ họa giảm 10%", groups=["Thiết kế đồ họa"])])
        c.facts = build_facts("DH-PTS", CAT, [promo("Đồ họa giảm 10%", groups=["Thiết kế đồ họa"])], None,
                              brand="EduFlow Academy")
        c.prompts = []
        c.writer = lambda prompt, system="": c.prompts.append((prompt, system)) or answer
        return c

    def good(self):
        return ('{"public": "Dạ em cảm ơn anh/chị Lan ạ, em đã nhắn tin riêng, anh/chị xem Messenger giúp em nhé.", '
                '"private": "Dạ em chào anh/chị Lan ạ. Khóa Photoshop cơ bản học phí 1.800.000đ, đang giảm còn '
                '1.620.000đ ạ. Anh/chị trả lời tin này để em giữ suất học thử nhé ạ."}')

    def test_good_gemini_replies_are_sent_and_marked(self):
        c, sender = self.ctx_with(self.good()), FakeSender()
        row = cf.handle(comment("học phí bao nhiêu ạ"), 33, c, sender, PAGE, NOW)
        self.assertEqual(row["writer"], "gemini")
        self.assertIn("1.620.000đ", row["private_reply"])
        self.assertIn('nhắn "test photoshop"', row["private_reply"])  # the level test is always offered
        prompt, system = c.prompts[0]
        self.assertIn("EduFlow Academy", prompt)
        self.assertIn("học phí bao nhiêu", prompt)
        self.assertIn("không bịa", system)

    def test_an_invented_price_falls_back_to_the_template(self):
        bad = self.good().replace("1.620.000đ", "990.000đ")
        row = cf.handle(comment("học phí bao nhiêu ạ"), 33, self.ctx_with(bad), FakeSender(), PAGE, NOW)
        self.assertEqual(row["writer"], "mixed")
        self.assertNotIn("990.000đ", row["private_reply"])
        self.assertIn("Dạ em chào anh/chị Lan Anh ạ", row["private_reply"])  # the template

    def test_wrong_pronoun_link_or_garbage_is_never_sent(self):
        self.assertIn("xưng hô", cf.acceptable("Dạ chào bạn ạ", {}, 300))
        self.assertEqual(cf.acceptable("Dạ xem tại https://x.vn ạ", {}, 300), "có đường link")
        for answer in ("không phải json", None, "{}"):
            row = cf.handle(comment("tư vấn em"), 33, self.ctx_with(answer), FakeSender(), PAGE, NOW)
            self.assertEqual(row["writer"], "template", answer)

    def test_a_public_reply_never_shows_a_price(self):
        leaky = self.good().replace("em đã nhắn tin riêng", "khóa chỉ 1.620.000đ, em đã nhắn tin riêng")
        row = cf.handle(comment("học phí bao nhiêu ạ"), 33, self.ctx_with(leaky), FakeSender(), PAGE, NOW)
        self.assertNotIn("1.620.000đ", row["public_reply"])  # the template answered in public
        self.assertIn("1.620.000đ", row["private_reply"])  # the price stays in the private message
        self.assertEqual(cf.acceptable("Dạ giảm 10% ạ", {}, 300, public=True), "nêu giá công khai")
        self.assertIn("KHÔNG nêu học phí", self.ctx_with(self.good()).writer and cf.writer_prompt(
            "price", "Lan", "giá?", self.ctx_with(self.good()), True, True))

    def test_every_private_reply_ends_with_how_to_register(self):
        for c in (self.ctx_with(self.good()), ctx()):  # Gemini and template
            row = cf.handle(comment("tư vấn em"), 33, c, FakeSender(), PAGE, NOW)
            self.assertTrue(row["private_reply"].endswith(cf.REGISTER_HINT), row["private_reply"])
            self.assertEqual(row["writer"], "gemini" if c.writer else "template")
            # the quoted phrase is what the customer types; the rest keeps the house tone
            self.assertEqual(problems(row["private_reply"].replace(cf.REGISTER_HINT, "")), [])
        self.assertEqual(cf.with_register_hint("Dạ nhắn tôi muốn đăng ký học nhé ạ"), "Dạ nhắn tôi muốn đăng ký học nhé ạ")

    def test_no_writer_means_templates(self):
        row = cf.handle(comment("hay quá"), 33, ctx(), FakeSender(), PAGE, NOW)
        self.assertEqual(row["writer"], "template")


class TestFailureNote(unittest.TestCase):
    def test_no_failure_no_note(self):
        self.assertEqual(cf.failure_note([{"status": "Replied"}, {"status": "Skipped"}]), "")

    def test_failures_are_counted_with_the_first_error(self):
        rows = [{"status": "Failed", "error": "private reply: (#10900) already replied", "from_name": "Lan"},
                {"status": "Failed", "error": "public reply: token expired", "from_name": "Minh"},
                {"status": "Replied"}]
        note = cf.failure_note(rows)
        self.assertIn("2 bình luận chưa trả lời được", note)
        self.assertIn("Lan", note)
        self.assertIn("10900", note)


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
