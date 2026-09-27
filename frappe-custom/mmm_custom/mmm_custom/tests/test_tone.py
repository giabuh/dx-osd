import json
import sys
from pathlib import Path
import unittest

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom.engine import tone

DATA = APP_DIR / "mmm_custom" / "demo" / "saoviet"
INTERNAL = {"summary_template"}  # the private handoff note is for consultants, not customers


def customer_templates():
    settings = json.loads((DATA / "settings.json").read_text(encoding="utf-8"))
    for key, text in settings.items():
        if key.endswith("_template") and key not in INTERNAL and isinstance(text, str):
            yield f"settings.{key}", text
    for skill in json.loads((DATA / "bot_skills.json").read_text(encoding="utf-8")):
        for t in skill.get("templates") or []:
            yield f"{skill['skill_key']}.{t['variant_key']}", t["template"]
    for slot in json.loads((DATA / "bot_slots.json").read_text(encoding="utf-8")):
        if slot.get("ask_template"):
            yield f"slot.{slot['slot_key']}", slot["ask_template"]


class TestTone(unittest.TestCase):
    def test_every_demo_template_keeps_the_house_tone(self):
        bad = {name: tone.problems(text) for name, text in customer_templates() if tone.problems(text)}
        self.assertEqual(bad, {})

    def test_rules(self):
        self.assertEqual(tone.problems("Dạ {{ brand.me }} gửi {{ brand.you }} lịch học ạ 😊"), [])
        self.assertEqual(tone.problems("{{ brand.you | capitalize }} muốn học ca nào ạ?"), [])
        self.assertTrue(tone.problems("Dạ mình gửi bạn lịch học ạ"))  # hard-coded pronouns
        self.assertTrue(tone.problems("Lịch học đây ạ"))  # abrupt opening
        self.assertTrue(tone.problems("Dạ lịch học đây"))  # no "ạ"
        self.assertTrue(tone.problems("Dạ xong rồi ạ 🎉🎉"))  # too many emoji

    def test_pronouns_only_as_whole_words(self):
        self.assertEqual(tone.problems("Dạ lớp tối thứ 3 khai giảng ạ"), [])
        self.assertIn("xưng hô viết cứng: bạn", tone.problems("Dạ bạn học lớp tối nhé ạ")[0])

if __name__ == "__main__":
    unittest.main()
