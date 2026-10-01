import sys
from datetime import datetime, timedelta
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from mmm_custom import task_dispatch as td

NOW = datetime(2026, 10, 1, 9, 0)


def person(user, branch="CN Bình Thạnh", level="Consultant", specialties=(), agent=1):
    return {"name": user, "full_name": user.split("@")[0].title(), "branch": branch, "level": level,
            "specialties": list(specialties), "handles_b2b": 0, "active": 1, "chatwoot_agent_id": agent}


MAI = person("mai@x", level="Team Lead", agent=1)
NAM = person("nam@x", agent=2)
HUNG = person("hung@x", branch="CN Dĩ An", agent=3)
PEOPLE = [MAI, NAM, HUNG]


def task(name, assignee, due_hours=48, status="Todo", priority="Medium", ref="CRM Lead", **kw):
    return {"name": name, "title": f"Task {name}", "status": status, "priority": priority, "assigned_to": assignee,
            "due_date": NOW + timedelta(hours=due_hours) if due_hours is not None else None,
            "reference_doctype": ref, "reference_docname": "LEAD-1" if ref else "", "proposal_status": "",
            "proposal_at": None, **kw}


CTX = {"branch": "CN Bình Thạnh", "group": "", "hot": False}


class TestScope(unittest.TestCase):
    def test_only_open_customer_tasks(self):
        self.assertTrue(td.in_scope(task(1, "mai@x")))
        self.assertTrue(td.in_scope(task(1, "mai@x", ref="CRM Deal")))
        self.assertFalse(td.in_scope(task(1, "mai@x", ref="")))
        self.assertFalse(td.in_scope(task(1, "mai@x", ref=None)))
        self.assertFalse(td.in_scope(task(1, "mai@x", status="Done")))
        self.assertFalse(td.in_scope(task(1, "mai@x", status="Canceled")))
        self.assertFalse(td.in_scope(task(1, "Administrator")))


class TestProblem(unittest.TestCase):
    def prob(self, t, load=None, online=None):
        return td.problem(t, {p["name"]: p for p in PEOPLE}, load or {}, online, NOW, td.CONFIG)

    def test_unassigned(self):
        self.assertEqual(self.prob(task(1, None))[0], "unassigned")
        self.assertEqual(self.prob(task(1, ""))[0], "unassigned")

    def test_assignee_who_is_not_a_consultant(self):
        code, why = self.prob(task(1, "nam.quan1@eduflow.vn"))
        self.assertEqual(code, "not_consultant")
        self.assertIn("nam.quan1@eduflow.vn", why)

    def test_inactive_consultant_counts_as_gone(self):
        gone = {**NAM, "active": 0}
        got = td.problem(task(1, "nam@x"), {"nam@x": gone}, {}, None, NOW, td.CONFIG)
        self.assertEqual(got[0], "not_consultant")

    def test_offline_and_urgent(self):
        code, why = self.prob(task(1, "mai@x", due_hours=5), online={"2", "3"})
        self.assertEqual(code, "offline")
        self.assertIn("Mai", why)
        self.assertEqual(self.prob(task(1, "mai@x", due_hours=-30), online={"2"})[0], "offline")

    def test_offline_but_not_urgent_or_online_or_unknown(self):
        self.assertIsNone(self.prob(task(1, "mai@x", due_hours=72), online={"2"}))
        self.assertIsNone(self.prob(task(1, "mai@x", due_hours=5), online={"1"}))
        self.assertIsNone(self.prob(task(1, "mai@x", due_hours=5), online=None))  # presence unknown: no guess
        self.assertIsNone(self.prob(task(1, "mai@x", due_hours=None), online={"2"}))

    def test_overloaded(self):
        code, why = self.prob(task(1, "mai@x"), load={"mai@x": 9})
        self.assertEqual(code, "overloaded")
        self.assertIn("9 việc", why)
        self.assertIsNone(self.prob(task(1, "mai@x"), load={"mai@x": 7}))

    def test_fine(self):
        self.assertIsNone(self.prob(task(1, "mai@x"), load={"mai@x": 2}, online={"1"}))


class TestBuild(unittest.TestCase):
    def build(self, tasks, ctx=None, online=None, people=PEOPLE, **kw):
        return td.build_proposals(tasks, ctx or {}, people, online, NOW, **kw)

    def test_unassigned_goes_to_the_branch_consultant_with_a_reason(self):
        got = self.build([task(1, None)], {1: CTX})
        self.assertEqual(len(got), 1)
        p = got[0]
        self.assertEqual((p["task"], p["from"], p["code"]), (1, None, "unassigned"))
        self.assertIn(p["to"], ("mai@x", "nam@x"))  # the Bình Thạnh branch, never Dĩ An
        self.assertTrue(p["reason"].startswith("Chưa có người phụ trách → giao "))
        self.assertIn("CN Bình Thạnh", p["reason"])
        self.assertIn(p["to_name"], p["reason"])

    def test_branch_group_and_hot_narrow_the_choice(self):
        people = [person("a@x", specialties=["Tin học văn phòng"], agent=1),
                  person("b@x", level="Team Lead", agent=2), person("c@x", agent=3)]
        group = self.build([task(1, None)], {1: {**CTX, "group": "Tin học văn phòng"}}, people=people)
        self.assertEqual(group[0]["to"], "a@x")
        self.assertIn("chuyên Tin học văn phòng", group[0]["reason"])
        hot = self.build([task(1, None)], {1: {**CTX, "hot": True}}, people=people)
        self.assertEqual(hot[0]["to"], "b@x")

    def test_a_swamped_person_gets_no_more_work_while_someone_has_room(self):
        """The hot customer's task would go to the only team lead, who already holds 9 open tasks."""
        busy = [task(i, "mai@x") for i in range(10, 19)]
        got = self.build([task(1, None)] + busy, {1: {**CTX, "hot": True}})
        first = next(p for p in got if p["task"] == 1)
        self.assertEqual(first["to"], "nam@x")
        # when everyone is swamped the task still gets a proposal (a person decides)
        all_busy = busy + [task(i, "nam@x") for i in range(30, 39)]
        got = self.build([task(1, None)] + all_busy, {1: CTX})
        self.assertTrue(any(p["task"] == 1 for p in got))

    def test_reason_does_not_capitalise_an_email(self):
        got = self.build([task(1, "nam.quan1@eduflow.vn")], {1: CTX})
        self.assertTrue(got[0]["reason"].startswith("Người phụ trách nam.quan1@eduflow.vn không còn"))

    def test_never_back_to_the_same_person(self):
        got = self.build([task(1, "mai@x", due_hours=2)], {1: CTX}, online={"1", "2"} - {"1"})
        self.assertEqual(got[0]["code"], "offline")
        self.assertEqual(got[0]["to"], "nam@x")

    def test_prefers_people_on_duty(self):
        people = [person("a@x", agent=1), person("b@x", agent=2)]
        got = self.build([task(1, None)], {1: CTX}, online={"2"}, people=people)
        self.assertEqual(got[0]["to"], "b@x")
        self.assertIn("đang trực", got[0]["reason"])

    def test_overload_needs_a_clearly_lighter_colleague(self):
        tasks = [task(i, "mai@x") for i in range(1, 10)] + [task(20, "nam@x"), task(21, "nam@x"), task(22, "nam@x")]
        ctx = {i: CTX for i in range(1, 30)}
        got = self.build(tasks, ctx)
        self.assertTrue(got)
        self.assertTrue(all(p["code"] == "overloaded" and p["from"] == "mai@x" and p["to"] == "nam@x" for p in got))
        # nam holds 3: moving more than a couple would leave mai (9 - k) lighter than nam (3 + k)
        self.assertLessEqual(len(got), 3)
        close = [task(i, "mai@x") for i in range(1, 9)] + [task(i + 10, "nam@x") for i in range(7)]
        self.assertEqual(self.build(close, {i: CTX for i in range(1, 30)}), [])

    def test_load_is_simulated_so_one_person_does_not_get_everything(self):
        tasks = [task(i, None) for i in range(1, 7)]
        got = self.build(tasks, {i: CTX for i in range(1, 7)})
        counts = {}
        for p in got:
            counts[p["to"]] = counts.get(p["to"], 0) + 1
        self.assertEqual(sorted(counts.values()), [3, 3])

    def test_most_urgent_first_and_limit(self):
        tasks = [task(1, None, due_hours=100), task(2, None, due_hours=-5), task(3, None, due_hours=10, priority="High"),
                 task(4, None, due_hours=10, priority="Low"), task(5, None, due_hours=None)]
        ctx = {i: CTX for i in range(1, 6)}
        self.assertEqual([p["task"] for p in self.build(tasks, ctx)], [2, 3, 4, 1, 5])
        self.assertEqual([p["task"] for p in self.build(tasks, ctx, limit=2)], [2, 3])

    def test_out_of_scope_and_hopeless_tasks_are_skipped(self):
        self.assertEqual(self.build([task(1, None, ref=""), task(2, "Administrator"), task(3, None, status="Done")], {}), [])
        self.assertEqual(self.build([task(1, None)], {1: CTX}, people=[]), [])  # nobody to give it to

    def test_pending_and_recently_rejected_are_not_proposed_again(self):
        pending = task(1, None, proposal_status="Pending", proposal_at=NOW - timedelta(hours=2))
        fresh = task(2, None, proposal_status="Rejected", proposal_at=NOW - timedelta(days=1))
        stale = task(3, None, proposal_status="Rejected", proposal_at=NOW - timedelta(days=4))
        got = self.build([pending, fresh, stale], {i: CTX for i in (1, 2, 3)})
        self.assertEqual([p["task"] for p in got], [3])

    def test_load_counts_every_open_task_of_a_person(self):
        tasks = [task(1, "mai@x"), task(2, "mai@x", ref=""), task(3, "mai@x", status="Done"), task(4, "nam@x")]
        self.assertEqual(td.open_load(tasks), {"mai@x": 2, "nam@x": 1})


class TestReminder(unittest.TestCase):
    def test_nothing_waiting_no_reminder(self):
        self.assertIsNone(td.reminder([], NOW))

    def test_counts_and_flags_old_proposals(self):
        rows = [{"proposal_at": NOW - timedelta(hours=2)}, {"proposal_at": NOW - timedelta(days=2)},
                {"proposal_at": None}]
        title, message = td.reminder(rows, NOW)
        self.assertEqual(title, "3 đề xuất giao việc chờ duyệt")
        self.assertIn("1 đề xuất đã chờ hơn 1 ngày", message)
        self.assertIn("trang Nhiệm vụ", message)
        _, fresh = td.reminder(rows[:1], NOW)
        self.assertNotIn("hơn 1 ngày", fresh)

    def test_an_unchanged_proposal_keeps_its_age(self):
        before = {7: ("nam@x", NOW - timedelta(days=2))}
        self.assertEqual(td.proposed_since(7, "nam@x", before, NOW), NOW - timedelta(days=2))
        self.assertEqual(td.proposed_since(7, "hoa@x", before, NOW), NOW)  # another person: a new proposal
        self.assertEqual(td.proposed_since(8, "nam@x", before, NOW), NOW)


class TestApproval(unittest.TestCase):
    def test_comment_texts(self):
        self.assertEqual(td.approval_comment("mai@x", "nam@x", "chưa có người", "boss@x"),
                         "Giao việc: mai@x → nam@x. Lý do: chưa có người. Duyệt bởi boss@x.")
        self.assertEqual(td.approval_comment(None, "nam@x", "x", "boss@x"),
                         "Giao việc: (chưa có) → nam@x. Lý do: x. Duyệt bởi boss@x.")
        self.assertEqual(td.rejection_comment("nam@x", "boss@x"),
                         "Từ chối đề xuất giao cho nam@x. Duyệt bởi boss@x.")

    def test_chosen_person_must_be_an_active_consultant(self):
        people = {p["name"]: p for p in PEOPLE}
        self.assertEqual(td.check_assignee("nam@x", people), "")
        self.assertIn("không phải tư vấn viên", td.check_assignee("ai-do@x", people))
        self.assertIn("không phải tư vấn viên", td.check_assignee("", people))


if __name__ == "__main__":
    unittest.main()
