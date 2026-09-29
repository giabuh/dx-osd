import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom import staff_sync
from mmm_custom.channels import PROVIDERS, api, facebook
from mmm_custom.chatwoot_client import ChatwootClient


def response(data, status=200):
    resp = MagicMock(status_code=status)
    resp.json.return_value = data
    return resp


class TestCredentialsAndUrls(unittest.TestCase):
    def test_both_app_values_are_required(self):
        self.assertEqual(facebook.app_credentials({"facebook_app_id": " 1 ", "facebook_app_secret": "s"}), ("1", "s"))
        for conf in ({}, {"facebook_app_id": "1"}, {"facebook_app_secret": "s"}):
            with self.assertRaises(ValueError):
                facebook.app_credentials(conf)

    def test_callback_url_is_this_site_unless_overridden(self):
        self.assertEqual(facebook.callback_url({}, "https://crm.example.vn/"),
                         "https://crm.example.vn/api/method/mmm_custom.channels.facebook.callback")
        self.assertEqual(facebook.callback_url({"facebook_redirect_uri": "https://x/cb"}, "http://127.0.0.1:8000"),
                         "https://x/cb")

    def test_auth_url_asks_for_page_messaging_and_lead_scopes(self):
        query = parse_qs(urlparse(facebook.auth_url("123", "https://x/cb", "st")).query)
        self.assertEqual(query["client_id"], ["123"])
        self.assertEqual(query["redirect_uri"], ["https://x/cb"])
        self.assertEqual(query["state"], ["st"])
        self.assertEqual(query["response_type"], ["code"])
        scopes = query["scope"][0].split(",")
        for scope in ("pages_show_list", "pages_messaging", "pages_manage_metadata", "leads_retrieval"):
            self.assertIn(scope, scopes)


class TestState(unittest.TestCase):
    def test_state_round_trip(self):
        state = facebook.make_state("secret", "a@x", 1000)
        self.assertTrue(facebook.state_ok("secret", state, "a@x", 1100))

    def test_other_user_secret_expired_or_garbage_refused(self):
        state = facebook.make_state("secret", "a@x", 1000)
        self.assertFalse(facebook.state_ok("secret", state, "b@x", 1100))
        self.assertFalse(facebook.state_ok("other", state, "a@x", 1100))
        self.assertFalse(facebook.state_ok("secret", state, "a@x", 1000 + facebook.STATE_TTL + 1))
        self.assertFalse(facebook.state_ok("secret", state, "a@x", 900))  # from the future
        for bad in (None, "", "abc", "1000.", ".sig"):
            self.assertFalse(facebook.state_ok("secret", bad, "a@x", 1100))


class TestGraph(unittest.TestCase):
    def test_error_carries_facebooks_message(self):
        http = MagicMock()
        http.get.return_value = response({"error": {"message": "Invalid OAuth access token."}}, 400)
        with self.assertRaisesRegex(facebook.GraphError, "Invalid OAuth"):
            facebook.graph_get(http, "me", {})

    def test_http_error_without_body(self):
        http = MagicMock()
        http.get.return_value = response(None, 500)
        with self.assertRaisesRegex(facebook.GraphError, "HTTP 500"):
            facebook.graph_get(http, "me", {})

    def test_code_then_long_lived_token(self):
        http = MagicMock()
        http.get.side_effect = [response({"access_token": "short"}), response({"access_token": "long"})]
        short = facebook.exchange_code(http, "1", "s", "https://x/cb", "CODE")
        self.assertEqual(facebook.long_lived_token(http, "1", "s", short), "long")
        first, second = http.get.call_args_list
        self.assertTrue(first.args[0].endswith("/oauth/access_token"))
        self.assertEqual(first.kwargs["params"]["code"], "CODE")
        self.assertEqual(second.kwargs["params"]["grant_type"], "fb_exchange_token")
        self.assertEqual(second.kwargs["params"]["fb_exchange_token"], "short")

    def test_list_pages_follows_paging(self):
        http = MagicMock()
        http.get.side_effect = [
            response({"data": [{"id": "1"}], "paging": {"next": "https://graph.facebook.com/v23.0/me/accounts?after=x"}}),
            response({"data": [{"id": "2"}], "paging": {}}),
        ]
        self.assertEqual([p["id"] for p in facebook.list_pages(http, "tok")], ["1", "2"])
        self.assertEqual(http.get.call_args_list[1].args[0], "https://graph.facebook.com/v23.0/me/accounts?after=x")


class TestPagePicker(unittest.TestCase):
    PAGES = [
        {"id": "1", "name": "Sao Việt Dĩ An", "category": "Education", "access_token": "SECRET",
         "tasks": ["ANALYZE", "MODERATE"], "picture": {"data": {"url": "https://img/1"}}},
        {"id": 2, "name": "Analyst only", "tasks": ["ANALYZE"]},
    ]

    def test_choices_mark_connected_pages_and_never_carry_tokens(self):
        rows = facebook.page_choices(self.PAGES, {"1": {"status": "Connected", "branch": "CN Dĩ An"}})
        self.assertEqual(rows[0], {"id": "1", "name": "Sao Việt Dĩ An", "category": "Education",
                                   "picture": "https://img/1", "can_message": True, "connected": True,
                                   "status": "Connected", "branch": "CN Dĩ An"})
        self.assertEqual((rows[1]["id"], rows[1]["can_message"], rows[1]["connected"]), ("2", False, False))
        self.assertNotIn("SECRET", repr(rows))

    def test_unknown_tasks_count_as_messaging(self):
        self.assertTrue(facebook.can_message({"id": "1"}))

    def test_selection_keeps_known_pages_and_branches(self):
        out = facebook.clean_selection('[{"id": "1", "branch": "CN Dĩ An"}, {"id": "1"}, {"id": 2}]',
                                       {"1": {}, "2": {}}, {"CN Dĩ An"})
        self.assertEqual(out, [{"id": "1", "branch": "CN Dĩ An"}, {"id": "2", "branch": ""}])

    def test_selection_refuses_foreign_page_unknown_branch_and_empty(self):
        with self.assertRaisesRegex(ValueError, "không quản lý"):
            facebook.clean_selection([{"id": "9"}], {"1": {}}, set())
        with self.assertRaisesRegex(ValueError, "Chi nhánh"):
            facebook.clean_selection([{"id": "1", "branch": "Nowhere"}], {"1": {}}, {"CN Dĩ An"})
        with self.assertRaises(ValueError):
            facebook.clean_selection([], {"1": {}}, set())


class TestHealth(unittest.TestCase):
    SCOPES = ["pages_messaging", "pages_manage_metadata", "pages_show_list"]

    def test_valid_page_token_that_never_expires(self):
        self.assertEqual(facebook.health({"is_valid": True, "expires_at": 0, "scopes": self.SCOPES}, 100),
                         ("Connected", "", None))

    def test_invalid_or_expired(self):
        status, error, _ = facebook.health({"is_valid": False, "error": {"message": "Session has expired"}}, 100)
        self.assertEqual((status, error), ("Token expired", "Session has expired"))
        self.assertEqual(facebook.health({"is_valid": True, "expires_at": 50, "scopes": self.SCOPES}, 100)[0],
                         "Token expired")

    def test_missing_permission(self):
        status, error, _ = facebook.health({"is_valid": True, "scopes": ["pages_show_list"]}, 100)
        self.assertEqual(status, "Error")
        self.assertIn("pages_messaging", error)


class TestChannelsApi(unittest.TestCase):
    def test_provider_cards_count_live_connections(self):
        cards = api.provider_cards(PROVIDERS, [{"provider": "Facebook", "status": "Connected"},
                                               {"provider": "Facebook", "status": "Token expired"},
                                               {"provider": "Facebook", "status": "Disconnected"}])
        by_key = {c["key"]: c for c in cards}
        self.assertEqual(by_key["facebook"]["connected"], 2)
        self.assertEqual(by_key["zalo"]["connected"], 0)
        self.assertEqual(by_key["facebook"]["status"], "live")
        self.assertEqual({by_key[k]["status"] for k in ("instagram", "zalo", "tiktok")}, {"soon"})

    def test_inbox_url(self):
        self.assertEqual(api.inbox_url("http://cw/", 1, 7), "http://cw/app/accounts/1/inbox/7")
        self.assertEqual(api.inbox_url("http://cw", 1, None), "")


class TestBranchInboxes(unittest.TestCase):
    CONSULTANTS = [
        {"email": "a@x", "branch": "CN Dĩ An"},
        {"email": "b@x", "branch": "CN Dĩ An"},
        {"email": "c@x", "branch": "CN Dĩ An", "active": 0},
        {"email": "d@x", "branch": "CN Thủ Đức"},
    ]
    IDS = {"a@x": 3, "b@x": 1, "d@x": 4}

    def test_connected_branch_pages_get_that_branchs_active_staff(self):
        plan = staff_sync.plan_branch_inboxes([
            {"status": "Connected", "branch": "CN Dĩ An", "chatwoot_inbox_id": 10},
            {"status": "Connected", "branch": "", "chatwoot_inbox_id": 11},  # shared page: handoff decides
            {"status": "Disconnected", "branch": "CN Thủ Đức", "chatwoot_inbox_id": 12},
            {"status": "Connected", "branch": "CN Thủ Đức", "chatwoot_inbox_id": None},
            {"status": "Connected", "branch": "CN Thủ Đức", "chatwoot_inbox_id": "13"},
        ], self.CONSULTANTS, self.IDS)
        self.assertEqual(plan, {10: [1, 3], 13: [4]})

    def test_sync_only_adds_members(self):
        client = MagicMock()
        self.assertEqual(staff_sync.sync_branch_inboxes(client, {10: [1, 3]}), 1)
        client.add_inbox_members.assert_called_once_with(10, [1, 3])


class TestChatwootClientChannels(unittest.TestCase):
    @patch("mmm_custom.chatwoot_client.requests")
    def test_connect_posts_page_token_to_fork_endpoint(self, requests):
        requests.post.return_value = response({"id": 7, "page_id": "1"})
        inbox = ChatwootClient("http://cw/", "tok", 1).connect_facebook_page("1", "PT", "UT", "Page")
        self.assertEqual(inbox["id"], 7)
        url = requests.post.call_args.args[0]
        self.assertEqual(url, "http://cw/api/v1/accounts/1/callbacks/connect_facebook_page")
        self.assertEqual(requests.post.call_args.kwargs["json"], {
            "page_id": "1", "page_access_token": "PT", "user_access_token": "UT", "inbox_name": "Page"})

    @patch("mmm_custom.chatwoot_client.requests")
    def test_disconnect(self, requests):
        requests.post.return_value = response({})
        ChatwootClient("http://cw", "tok", 1).disconnect_facebook_page("1")
        self.assertEqual(requests.post.call_args.args[0],
                         "http://cw/api/v1/accounts/1/callbacks/disconnect_facebook_page")


if __name__ == "__main__":
    unittest.main()
