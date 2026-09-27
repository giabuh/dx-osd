import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine_fixtures  # noqa: F401

from mmm_custom.engine.jev import JevClient, jev_client


class ConnectionError(Exception):  # same name as requests' ConnectionError, which the client retries
    pass


def response(data, status=200):
    r = MagicMock()
    r.json.return_value = data
    r.raise_for_status.side_effect = None if status == 200 else RuntimeError(f"HTTP {status}")
    return r


OK = {"model": "jev-1.13.0", "answers": {"intent": {"type": "choice", "choice": "price", "confidence": 1.0}},
      "usage": {"input_tokens": 344}}
Q = {"intent": {"type": "choice", "instructions": "x", "criteria": {"price": "p"}}}


class TestClient(unittest.TestCase):
    def test_ok_answer_with_model_and_tokens(self):
        post = MagicMock(return_value=response(OK))
        r = JevClient("k", post=post).ask({"latest_message": "hp?"}, Q)
        self.assertEqual((r.status, r.model, r.input_tokens), ("ok", "jev-1.13.0", 344))
        self.assertEqual(r.answers["intent"]["choice"], "price")
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["headers"], {"Authorization": "Bearer k"})
        self.assertEqual(kwargs["json"]["questions"], Q)
        self.assertLessEqual(kwargs["timeout"], 8.0)

    def test_dropped_connection_is_retried_once(self):
        post = MagicMock(side_effect=[ConnectionError("Remote end closed"), response(OK)])
        self.assertEqual(JevClient("k", post=post).ask({}, Q).status, "ok")
        self.assertEqual(post.call_count, 2)

    def test_other_errors_are_unavailable_without_retry(self):
        post = MagicMock(return_value=response({}, status=500))
        r = JevClient("k", post=post).ask({}, Q)
        self.assertEqual((r.status, post.call_count), ("unavailable", 1))
        self.assertIn("HTTP 500", r.error)

    def test_malformed_response_is_unavailable(self):
        bad = MagicMock()
        bad.raise_for_status.side_effect = None
        bad.json.side_effect = ValueError("not json")
        self.assertEqual(JevClient("k", post=MagicMock(return_value=bad)).ask({}, Q).status, "unavailable")

    def test_no_questions_no_call(self):
        post = MagicMock()
        self.assertEqual(JevClient("k", post=post).ask({}, {}).status, "ok")
        post.assert_not_called()

    def test_log_shape(self):
        r = JevClient("k", post=MagicMock(return_value=response(OK))).ask({}, Q)
        self.assertEqual(set(r.log()), {"status", "questions", "answers", "model", "latency_ms", "input_tokens", "error"})


class TestFactory(unittest.TestCase):
    def test_key_and_switches(self):
        self.assertIsNone(jev_client({}, {"jev_live": 1}))
        self.assertIsNone(jev_client({"typesafe_api_key": "k"}, {"jev_live": 0}))
        self.assertIsNotNone(jev_client({"typesafe_api_key": "k"}, {"jev_live": 1}))
        self.assertIsNone(jev_client({"typesafe_api_key": "k"}, {"jev_live": 1}, force=False))
        c = jev_client({"typesafe_api_key": "k", "typesafe_model": "jev-x"}, {"jev_live": 0, "jev_timeout": 5}, force=True)
        self.assertEqual((c.model, c.timeout), ("jev-x", 5.0))


if __name__ == "__main__":
    unittest.main()
