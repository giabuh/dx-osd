import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import dataclasses
from mmm_custom.chatwoot_client import ChatwootClient
from mmm_custom.engine.decide import Decision
from mmm_custom.engine.effects import ChatwootEffects, RecordingEffects
from mmm_custom.engine.reply import Reply, compose
from mmm_custom.engine.state import ConversationState

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))
from engine_fixtures import demo_catalog, fill, render


class TestChatwootClientTyping(unittest.TestCase):
    def setUp(self):
        self.client = ChatwootClient("https://chatwoot.test", "dummy-token", 1)

    @patch("mmm_custom.chatwoot_client.requests.post")
    def test_toggle_typing_default(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "ok"}
        mock_post.return_value = mock_resp

        res = self.client.toggle_typing(101)

        mock_post.assert_called_once_with(
            "https://chatwoot.test/api/v1/accounts/1/conversations/101/toggle_typing_status",
            headers={"api_access_token": "dummy-token"},
            json={"typing_status": "on"},
            timeout=3,
        )
        mock_resp.raise_for_status.assert_called_once()
        self.assertEqual(res, {"status": "ok"})

    @patch("mmm_custom.chatwoot_client.requests.post")
    def test_toggle_typing_off(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "ok"}
        mock_post.return_value = mock_resp

        res = self.client.toggle_typing(101, status="off")

        mock_post.assert_called_once_with(
            "https://chatwoot.test/api/v1/accounts/1/conversations/101/toggle_typing_status",
            headers={"api_access_token": "dummy-token"},
            json={"typing_status": "off"},
            timeout=3,
        )
        self.assertEqual(res, {"status": "ok"})


class TestRecordingEffectsTyping(unittest.TestCase):
    def test_toggle_typing(self):
        rec = RecordingEffects()
        rec.toggle_typing(123, "on")
        rec.toggle_typing("456", "off")

        self.assertEqual(rec.calls, [
            ("toggle_typing", {"conversation_id": "123", "status": "on"}),
            ("toggle_typing", {"conversation_id": "456", "status": "off"}),
        ])


class TestChatwootEffectsSend(unittest.TestCase):
    def setUp(self):
        self.bot = MagicMock()
        self.user = MagicMock()
        self.effects = ChatwootEffects(self.bot, self.user)

    @patch("time.sleep")
    def test_send_activates_typing_and_calculates_delay_min(self, mock_sleep):
        reply = Reply(messages=["Xin chào!"])  # len = 9, 9 * 0.012 = 0.108 -> min clamp 1.5

        self.effects.send(101, reply)

        self.bot.toggle_typing.assert_called_once_with(101, "on")
        mock_sleep.assert_called_once_with(1.5)
        self.bot.send_message.assert_called_once_with(101, "Xin chào!")

    @patch("time.sleep")
    def test_send_calculates_delay_max(self, mock_sleep):
        long_text = "A" * 300  # len = 300, 300 * 0.012 = 3.6 -> max clamp 2.5
        reply = Reply(messages=[long_text])

        self.effects.send(101, reply)

        mock_sleep.assert_called_once_with(2.5)

    @patch("time.sleep")
    def test_send_calculates_delay_proportional(self, mock_sleep):
        text = "A" * 150  # len = 150, 150 * 0.012 = 1.8 -> clamped 1.8
        reply = Reply(messages=[text])

        self.effects.send(101, reply)

        mock_sleep.assert_called_once_with(1.8)

    @patch("time.sleep")
    def test_send_typing_error_is_swallowed(self, mock_sleep):
        self.bot.toggle_typing.side_effect = RuntimeError("Chatwoot unreachable")
        reply = Reply(messages=["Chào bạn"])

        # Should not raise exception
        self.effects.send(101, reply)

        self.bot.send_message.assert_called_once_with(101, "Chào bạn")

    @patch("time.sleep")
    def test_send_dispatches_media_attachments(self, mock_sleep):
        reply = Reply(
            messages=["Đây là ảnh lớp học:"],
            attachments=[
                {"type": "image", "url": "https://example.com/lop-hoc.jpg", "title": "Lớp Tin học"},
                {"type": "image", "url": "https://example.com/no-title.jpg"},
                {"type": "video", "url": "https://example.com/video.mp4"},  # non-image ignored
                {"type": "image"},  # missing url ignored
            ]
        )

        self.effects.send(101, reply)

        # Expected attachment calls before the message call
        expected_attachment_calls = [
            unittest.mock.call(
                101,
                "![Lớp Tin học](https://example.com/lop-hoc.jpg)",
                content_attributes={"image_url": "https://example.com/lop-hoc.jpg"}
            ),
            unittest.mock.call(
                101,
                "![Hình ảnh](https://example.com/no-title.jpg)",
                content_attributes={"image_url": "https://example.com/no-title.jpg"}
            ),
            unittest.mock.call(101, "Đây là ảnh lớp học:"),
        ]
        self.assertEqual(self.bot.send_message.call_args_list, expected_attachment_calls)

    @patch("time.sleep")
    def test_send_dispatches_quick_replies_on_last_message(self, mock_sleep):
        reply = Reply(
            messages=["Chào bạn!", "Bạn muốn tư vấn khoá nào?"],
            buttons=[{"title": "Excel"}, {"title": "Word"}],
        )

        self.effects.send(101, reply)

        self.bot.send_message.assert_called_once_with(101, "Chào bạn!")
        self.bot.send_quick_replies.assert_called_once_with(
            101,
            "Bạn muốn tư vấn khoá nào?",
            [{"title": "Excel", "value": "Excel"}, {"title": "Word", "value": "Word"}],
        )


class TestReplyComposeCourseAttachment(unittest.TestCase):
    def setUp(self):
        self.cat = demo_catalog()
        course = dataclasses.replace(
            self.cat.courses["VP-EXCEL"],
            image="https://example.com/excel-brochure.jpg"
        )
        self.cat = dataclasses.replace(self.cat, courses={**self.cat.courses, "VP-EXCEL": course})

    def test_reply_compose_attaches_course_image(self):
        decision = Decision("answer", slots={"course": fill("VP-EXCEL")}, skills=["fee_quote"])
        state = ConversationState("1", turns=1)
        reply = compose(decision, state, self.cat, render)

        self.assertTrue(any(
            att.get("type") == "image" and att.get("url") == "https://example.com/excel-brochure.jpg"
            for att in reply.attachments
        ))
        excel_att = next(att for att in reply.attachments if att.get("url") == "https://example.com/excel-brochure.jpg")
        self.assertEqual(excel_att, {
            "type": "image",
            "url": "https://example.com/excel-brochure.jpg",
            "title": self.cat.courses["VP-EXCEL"].name,
        })

    def test_reply_compose_attaches_course_image_from_dict_slot(self):
        decision = Decision("answer", slots={"course": {"value": "VP-EXCEL"}}, skills=["fee_quote"])
        state = ConversationState("1", turns=1)
        reply = compose(decision, state, self.cat, render)
        self.assertTrue(any(
            att.get("url") == "https://example.com/excel-brochure.jpg"
            for att in reply.attachments
        ))

    def test_reply_compose_no_image_when_course_has_no_image(self):
        decision = Decision("answer", slots={"course": fill("VP-WORD")}, skills=["fee_quote"])
        state = ConversationState("1", turns=1)
        reply = compose(decision, state, self.cat, render)
        self.assertEqual(reply.attachments, [])

    def test_reply_compose_attaches_course_image_from_state_slots(self):
        decision = Decision("answer", slots={}, skills=["duration"])
        state = ConversationState("1", turns=1, slots={"course": fill("VP-EXCEL")})
        reply = compose(decision, state, self.cat, render)
        self.assertTrue(any(
            att.get("url") == "https://example.com/excel-brochure.jpg"
            for att in reply.attachments
        ))

    def test_reply_compose_attaches_course_image_dict_course(self):
        cat_mock = MagicMock()
        cat_mock.settings = self.cat.settings
        cat_mock.slots = []
        cat_mock.slot_for.return_value = None
        cat_mock.branches = self.cat.branches
        cat_mock.skills = self.cat.skills
        cat_mock.courses = {
            "CUSTOM-COURSE": {
                "image": "https://example.com/custom.png",
                "product_name": "Khoá học Custom",
            }
        }
        decision = Decision("answer", slots={"course": "CUSTOM-COURSE"})
        state = ConversationState("1")
        reply = compose(decision, state, cat_mock, render)
        self.assertIn({
            "type": "image",
            "url": "https://example.com/custom.png",
            "title": "Khoá học Custom",
        }, reply.attachments)


if __name__ == "__main__":
    unittest.main()

