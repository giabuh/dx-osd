import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import FakeRepo, demo_catalog, render

from mmm_custom import sources
from mmm_custom.engine.effects import RecordingEffects
from mmm_custom.engine.pipeline import parse_event, run_turn

CAT = demo_catalog()


def payload(text, message_id, channel="Channel::FacebookPage", extra=None):
    return {"event": "message_created", "id": message_id, "content": text, "message_type": "incoming", "private": False,
            "sender": {"id": 9, "type": "contact"},
            "conversation": {"id": 7, "inbox_id": 3, "channel": channel, "additional_attributes": extra or {},
                             "meta": {"sender": {"id": 9, "name": "Lan"}}}}


class TestChannels(unittest.TestCase):
    def test_chatwoot_channel_types_map_to_channels(self):
        self.assertEqual(sources.channel_key({"channel": "Channel::FacebookPage"}), "facebook_messenger")
        self.assertEqual(sources.channel_key({"channel": "Channel::WebWidget"}), "website")
        self.assertEqual(sources.channel_key({"channel": "Channel::Email"}), "")
        self.assertEqual(sources.channel_key(None), "")

    def test_instagram_through_a_facebook_page(self):
        conv = {"channel": "Channel::FacebookPage", "additional_attributes": {"type": "instagram_direct_message"}}
        self.assertEqual(sources.channel_key(conv), "instagram")

    def test_api_inbox_adapter_names_its_channel(self):
        conv = {"channel": "Channel::Api", "additional_attributes": {"channel_key": "zalo", "campaign": "OA tháng 10"}}
        self.assertEqual((sources.channel_key(conv), sources.campaign_of(conv)), ("zalo", "OA tháng 10"))
        self.assertEqual(sources.channel_key({"channel": "Channel::Api", "additional_attributes": {"channel_key": "x"}}), "")

    def test_legacy_source_names_belong_to_messenger(self):
        self.assertEqual(sources.channel_of_source("Messenger Bot"), "facebook_messenger")
        self.assertEqual(sources.channel_of_source("Facebook"), "facebook_lead_ads")
        self.assertEqual(sources.channel_of_source("Báo giấy"), "")

    def test_keys_and_source_names_are_unique(self):
        for key in ("key", "source"):
            values = [c[key] for c in sources.CHANNELS]
            self.assertEqual(len(values), len(set(values)))
        self.assertTrue(all(c["status"] in ("live", "ready", "planned", "manual") for c in sources.CHANNELS))


class TestLeadSource(unittest.TestCase):
    def test_new_lead_records_its_channel_once(self):
        repo, fx = FakeRepo(CAT), RecordingEffects()
        widget = {"referer": "https://tinhocsaoviet.com/khoa-hoc/excel"}
        run_turn(parse_event(payload("Mình ở Quận 6 muốn học Excel", 1, "Channel::WebWidget", widget)), repo, fx, render)
        repo.states["7"].lead = "CRM-LEAD-1"  # the first save created it
        run_turn(parse_event(payload("0923456789", 2, "Channel::WebWidget", widget)), repo, fx, render)
        first, second = [row["fields"] for row in fx.of("save_lead")]
        self.assertEqual((first["source"], first["source_campaign"]), ("Website", "https://tinhocsaoviet.com/khoa-hoc/excel"))
        self.assertNotIn("source", second)

    def test_unknown_channel_sets_no_source(self):
        repo, fx = FakeRepo(CAT), RecordingEffects()
        run_turn(parse_event(payload("Mình ở Quận 6 muốn học Excel", 1, "")), repo, fx, render)
        self.assertNotIn("source", fx.of("save_lead")[0]["fields"])


if __name__ == "__main__":
    unittest.main()
