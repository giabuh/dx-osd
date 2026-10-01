import sys
from datetime import date
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from engine_fixtures import demo_catalog, promo

from mmm_custom import marketing_plan as mp

CAT = demo_catalog()
TODAY = date(2026, 10, 1)


def cand(code, group, **kw):
    return {"code": code, "name": code, "group": group, "next_class": None, "promo": "", "leads": 0,
            "registrations": 0, "last_planned": None, **kw}


class TestScore(unittest.TestCase):
    def test_signals_add_up_with_reasons(self):
        c = cand("VP-EXCEL", "VP", next_class={"date": date(2026, 10, 12), "seats": 6, "branch": "CN Dĩ An"},
                 promo="Excel giảm 10%", leads=5, registrations=1, last_planned=date(2026, 8, 1))
        points, reasons = mp.score(c, TODAY)
        self.assertEqual(points, 4 + 2 + 3 + 2 + 1)
        text = " · ".join(reasons)
        for part in ("12/10", "6 chỗ", "Excel giảm 10%", "5 khách tiềm năng", "1 học viên", "lâu chưa đăng"):
            self.assertIn(part, text)

    def test_far_or_full_class_does_not_count(self):
        far = cand("A", "g", next_class={"date": date(2026, 11, 20), "seats": 5, "branch": ""})
        full = cand("B", "g", next_class={"date": date(2026, 10, 5), "seats": 0, "branch": ""})
        self.assertEqual(mp.score(far, TODAY)[0], 1)  # only "lâu chưa đăng"
        self.assertEqual(mp.score(full, TODAY)[0], 1)

    def test_recently_posted_course_rests(self):
        c = cand("A", "g", promo="x", last_planned=date(2026, 9, 28))
        self.assertEqual(mp.score(c, TODAY)[0], 2 - 4)

    def test_caps(self):
        c = cand("A", "g", leads=40, registrations=9, last_planned=date(2026, 9, 10))
        self.assertEqual(mp.score(c, TODAY)[0], 3 + 4)


class TestPick(unittest.TestCase):
    def test_one_course_per_group_then_fill_deterministic(self):
        cands = [cand("A1", "A", promo="p", leads=3), cand("A2", "A", promo="p", leads=3),
                 cand("B1", "B", leads=1), cand("C1", "C"), cand("D1", "D")]
        picked = [p["code"] for p in mp.pick(cands, TODAY, 4)]
        self.assertEqual(len(picked), 4)
        self.assertEqual(len({c[0] for c in picked}), 4)  # four groups before a second course of a group
        self.assertEqual(mp.pick(cands, TODAY, 4), mp.pick(list(reversed(cands)), TODAY, 4))

    def test_equal_points_sooner_class_first(self):
        later = cand("A1", "A", next_class={"date": date(2026, 10, 9), "seats": 5, "branch": ""})
        sooner = cand("B1", "B", next_class={"date": date(2026, 10, 5), "seats": 5, "branch": ""})
        self.assertEqual([c["code"] for c in mp.pick([later, sooner], TODAY, 2)], ["B1", "A1"])

    def test_fill_from_same_group_when_short(self):
        cands = [cand("A1", "A"), cand("A2", "A"), cand("B1", "B")]
        self.assertEqual(len(mp.pick(cands, TODAY, 4)), 3)

    def test_promoted_course_takes_the_sunday_offer_slot(self):
        cands = [cand("A1", "A", leads=3, registrations=2), cand("B1", "B", leads=3), cand("C1", "C", leads=2),
                 cand("D1", "D", promo="Giảm 10%", leads=2)]
        picked = mp.pick(cands, TODAY, 4)
        slots = mp.assign_slots(picked, offer_slot=3)
        self.assertEqual(slots[3]["code"], "D1")
        self.assertEqual(slots[0]["code"], "A1")

    def test_title(self):
        c = cand("VP-EXCEL", "VP", next_class={"date": date(2026, 10, 12), "seats": 6, "branch": ""})
        c["name"] = "Excel cơ bản"
        self.assertEqual(mp.title_for(c), "Excel cơ bản – khai giảng 12/10")
        self.assertEqual(mp.title_for(cand("X", "g", name="Word")), "Word")


class TestFacts(unittest.TestCase):
    def setUp(self):
        self.facts = mp.build_facts("DH-PTS", CAT, [promo("Đồ họa giảm 10%", groups=["Thiết kế đồ họa"])],
                                    {"date": date(2026, 10, 12), "seats": 6, "branch": "CN Dĩ An"})

    def test_facts_come_from_the_catalog(self):
        f = self.facts
        self.assertEqual((f["brand"], f["hotline"]), ("Tin Học Sao Việt", "0931 144 858"))
        self.assertEqual(len(f["branches"]), len(CAT.branches))
        self.assertEqual(f["course"]["code"], "DH-PTS")
        self.assertEqual(f["promo"]["title"], "Đồ họa giảm 10%")
        self.assertEqual(f["quiz_keyword"], "test photoshop")
        text = "\n".join(mp.facts_lines(f))
        for part in ("Tin Học Sao Việt", "0931 144 858", "1.800.000đ", "1.620.000đ", "12/10", "CN Dĩ An",
                     "test photoshop"):
            self.assertIn(part, text)
        self.assertNotIn("0901", text)

    def test_unknown_course_still_has_brand_facts(self):
        f = mp.build_facts("Tiếng Anh", CAT, [], None)
        self.assertEqual(f["course"], {})
        self.assertIn("Tin Học Sao Việt", "\n".join(mp.facts_lines(f)))

    def test_cta_added_once(self):
        out = mp.ensure_cta("Học Photoshop cùng Sao Việt.", "test photoshop")
        self.assertIn('Bình luận "test photoshop"', out)
        self.assertEqual(mp.ensure_cta(out, "test photoshop"), out)
        self.assertEqual(mp.ensure_cta("Bài viết", ""), "Bài viết")
        self.assertEqual(mp.ensure_cta("Comment TEST PHOTOSHOP nhé", "test photoshop"), "Comment TEST PHOTOSHOP nhé")

    def test_unsupported_claims(self):
        ok = "Học phí chỉ còn 1.620.000đ, gọi 0931 144 858. Lớp 12/10, 3 lợi ích, năm 2026."
        self.assertEqual(mp.unsupported_claims(ok, self.facts), [])
        bad = "Giảm 50% chỉ còn 900.000đ! Gọi ngay 0901.888.666"
        found = mp.unsupported_claims(bad, self.facts)
        self.assertEqual(len(found), 3)
        self.assertTrue(any("50%" in x for x in found))
        self.assertTrue(any("900.000đ" in x for x in found))
        self.assertTrue(any("0901" in x for x in found))

    def test_promo_percent_from_its_title_is_allowed(self):
        self.assertEqual(mp.unsupported_claims("Đồ họa giảm 10% tuần này", self.facts), [])

    def test_caption_rules_carry_data_not_hard_coded_contacts(self):
        rules = mp.caption_rules(self.facts, "Photoshop cơ bản")
        for part in ("Tin Học Sao Việt", "0931 144 858", "1.620.000đ", "không bịa ưu đãi", 'bình luận "test photoshop"',
                     "#TinHocSaoViet", "#PhotoshopCoBan"):
            self.assertIn(part, rules)
        for gone in ("EduFlow", "0901", "CS1"):
            self.assertNotIn(gone, rules)
        bare = mp.caption_rules({}, "")
        self.assertIn("Không nêu số điện thoại", bare)
        self.assertIn("inbox fanpage", bare)

    def test_footer(self):
        self.assertEqual(mp.footer_text(self.facts),
                         f"Hotline: 0931 144 858  •  tinhocsaoviet.com  •  {len(CAT.branches)} chi nhánh")
        self.assertEqual(mp.footer_text({}), "Inbox fanpage để được tư vấn")


if __name__ == "__main__":
    unittest.main()
