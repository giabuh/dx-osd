import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import dataclasses
import requests
from mmm_custom.chatwoot_client import ChatwootClient
from mmm_custom.engine.decide import Decision
from mmm_custom.engine.effects import ChatwootEffects, RecordingEffects
from mmm_custom.engine.jev import JevClient, JevResult
from mmm_custom.engine.pipeline import understand_turn
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


class TestReturningCustomerMemory(unittest.TestCase):
    def setUp(self):
        self.cat = demo_catalog()

    def test_returning_customer_memory_context(self):
        from mmm_custom.engine.context import base_context

        state = ConversationState(
            "101",
            contact_id="12",
            lead="LEAD-001",
            is_returning=True,
            slots={
                "phone": fill("0901234567", source="lead"),
                "branch": fill("CN Dĩ An", source="lead"),
            },
        )
        state.customer_name = "Nguyễn Văn A"
        state.previous_course = "Tin học văn phòng"
        state.previous_branch = "CN Dĩ An"

        ctx = base_context(state.slots, self.cat, state)

        self.assertTrue(ctx["customer"]["is_returning"])
        self.assertEqual(ctx["customer"]["previous_course"], "Tin học văn phòng")
        self.assertEqual(ctx["customer"]["previous_branch"], "CN Dĩ An")
        self.assertEqual(ctx["customer"]["name"], "Nguyễn Văn A")
        self.assertEqual(ctx["slots"]["phone"], "0901234567")
        self.assertEqual(ctx["slots"]["branch"], "CN Dĩ An")

    @patch("mmm_custom.engine.repo.frappe")
    def test_new_state_returning_customer_prefills_slots_and_memory(self, mock_frappe):
        from mmm_custom.engine.repo import FrappeRepo
        from mmm_custom.engine.pipeline import Event

        repo = FrappeRepo()
        repo._catalog = self.cat

        event = Event(
            kind="customer_message",
            conversation_id="202",
            message_id=1,
            text="Chào trung tâm",
            contact={"id": "55", "name": "Khách Messenger"},
            inbox_id="1",
        )

        mock_frappe.db.exists.side_effect = lambda dt, name: True if dt == "CRM Lead" and name == "LEAD-55" else False
        mock_frappe.get_meta.return_value = MagicMock(has_field=lambda f: True)
        mock_frappe.db.count.return_value = 1

        def fake_get_value(doctype, name, fields=None, as_dict=False):
            if doctype == "CRM Lead" and name == "LEAD-55":
                if isinstance(fields, list) and "course_interest" in fields:
                    return {
                        "first_name": "Nguyễn Thị Mai",
                        "lead_name": "Nguyễn Thị Mai",
                        "course_interest": "Luyện thi MOS Excel",
                        "territory": "CN Dĩ An",
                        "mobile_no": "0912345678",
                    }
                return {"territory": "CN Dĩ An", "mobile_no": "0912345678"}
            return None

        mock_frappe.db.get_value.side_effect = fake_get_value

        with patch("mmm_custom.engine.repo.find_lead", return_value="LEAD-55"):
            state = repo.new_state(event)

        self.assertTrue(state.is_returning)
        self.assertEqual(state.customer_name, "Nguyễn Thị Mai")
        self.assertEqual(state.previous_course, "Luyện thi MOS Excel")
        self.assertEqual(state.previous_branch, "CN Dĩ An")
        self.assertEqual(state.slots["phone"]["value"], "0912345678")
        self.assertEqual(state.slots["branch"]["value"], "CN Dĩ An")

    @patch("mmm_custom.engine.repo.frappe")
    def test_new_state_returning_customer_does_not_overwrite_existing_slots(self, mock_frappe):
        from mmm_custom.engine.repo import FrappeRepo
        from mmm_custom.engine.pipeline import Event

        repo = FrappeRepo()
        repo._catalog = self.cat

        event = Event(
            kind="customer_message",
            conversation_id="203",
            message_id=2,
            text="Chào trung tâm",
            contact={"id": "56", "name": "Nguyễn Văn B"},
            inbox_id="1",
        )

        mock_frappe.db.exists.side_effect = lambda dt, name: True if dt == "CRM Lead" and name == "LEAD-56" else False
        mock_frappe.get_meta.return_value = MagicMock(has_field=lambda f: True)
        mock_frappe.db.count.return_value = 1

        def fake_get_value(doctype, name, fields=None, as_dict=False):
            if doctype == "CRM Lead" and name == "LEAD-56":
                if isinstance(fields, list) and "course_interest" in fields:
                    return {
                        "first_name": "Nguyễn Văn B",
                        "lead_name": "Nguyễn Văn B",
                        "course_interest": "Photoshop",
                        "territory": "CN Bình Thạnh",
                        "mobile_no": "0987654321",
                    }
                return {"territory": "CN Dĩ An", "mobile_no": "0911111111"}
            return None

        mock_frappe.db.get_value.side_effect = fake_get_value

        with patch("mmm_custom.engine.repo.find_lead", return_value="LEAD-56"):
            state = repo.new_state(event)

        self.assertTrue(state.is_returning)
        self.assertEqual(state.slots["phone"]["value"], "0911111111")
        self.assertEqual(state.slots["branch"]["value"], "CN Dĩ An")
        self.assertEqual(state.previous_course, "Photoshop")
        self.assertEqual(state.previous_branch, "CN Bình Thạnh")


class TestJevTimeoutAndFallback(unittest.TestCase):
    @patch("mmm_custom.engine.jev.requests.post")
    def test_jev_client_strict_timeout_and_fallback(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out after 2.5s")
        client = JevClient("test-key")
        result = client.ask({"latest_message": "học phí excel"}, {"intent": {"type": "choice"}})

        self.assertEqual(result.status, "timeout_fallback")
        self.assertIn("timed out after 2.5s", result.error)
        mock_post.assert_called_once()
        self.assertEqual(mock_post.call_args.kwargs.get("timeout"), 2.5)

    @patch("mmm_custom.engine.jev.requests.post")
    def test_pipeline_understand_turn_timeout_fallback(self, mock_post):
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out after 2.5s")
        client = JevClient("test-key")
        cat = demo_catalog()
        state = ConversationState("conv-123")
        text = "học phí khoá excel bạn ơi"

        u, jev_res = understand_turn(text, state, cat, client)

        self.assertEqual(jev_res.status, "timeout_fallback")
        self.assertIn("course", u.fills)
        self.assertEqual(u.fills["course"]["value"], "VP-EXCEL")


if __name__ == "__main__":
    unittest.main()


