import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import engine_fixtures  # noqa: F401  (puts the app on sys.path)

from mmm_custom.engine.text import content_words, find_phone, find_phrases, fold, normalize_vn_phone, plain_text, slug


class TestText(unittest.TestCase):
    def test_fold_strips_diacritics_case_and_punctuation(self):
        self.assertEqual(fold("Học phí Excel ở Dĩ An, Q.7?"), "hoc phi excel o di an q 7")
        self.assertEqual(fold("ĐỒ HỌA"), "do hoa")
        self.assertEqual(fold(None), "")

    def test_plain_text_from_editor_html(self):
        self.assertEqual(plain_text("<p>A&amp;B</p><ul><li>x</li><li>y</li></ul>"), "A&B x y")
        self.assertEqual(plain_text(None), "")

    def test_find_phrases_whole_words_only(self):
        self.assertEqual(find_phrases("hoc excel", {"X": ["excel"]}), {"X": (4, 9)})
        self.assertEqual(find_phrases("hoc excelsior", {"X": ["excel"]}), {})

    def test_longer_phrase_of_another_value_wins(self):
        table = {"EXCEL": ["excel"], "EXCEL-NC": ["excel nang cao"], "KT": ["ke toan excel"]}
        self.assertEqual(set(find_phrases(fold("Excel nâng cao"), table)), {"EXCEL-NC"})
        self.assertEqual(set(find_phrases(fold("kế toán excel"), table)), {"KT"})
        self.assertEqual(set(find_phrases(fold("excel va ke toan excel"), table)), {"EXCEL", "KT"})

    def test_min_words(self):
        self.assertEqual(find_phrases("toi muon hoc", {"evening": ["toi", "buoi toi"]}, min_words=2), {})
        self.assertIn("evening", find_phrases("hoc buoi toi", {"evening": ["toi", "buoi toi"]}, min_words=2))

    def test_phone(self):
        self.assertEqual(normalize_vn_phone("0901.234.567"), "+84901234567")
        self.assertEqual(normalize_vn_phone("+84 901 234 567"), "+84901234567")
        self.assertIsNone(normalize_vn_phone("12345"))
        self.assertEqual(find_phone("sdt em 0901 234 567 nha"), "+84901234567")
        self.assertIsNone(find_phone("lop 12 nguoi"))

    def test_slug_and_content_words(self):
        self.assertEqual(slug("CN Dĩ An"), "cn-di-an")
        folded = fold("abcxyz excel nha")
        spans = list(find_phrases(folded, {"X": ["excel"]}).values())
        self.assertEqual(content_words(folded, spans), ["abcxyz"])


if __name__ == "__main__":
    unittest.main()
