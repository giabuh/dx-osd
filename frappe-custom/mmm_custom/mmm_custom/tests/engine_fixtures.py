"""Shared offline fixtures for the lead-engine tests: the demo catalog and in-memory fakes."""

import copy
import sys
from datetime import date
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from mmm_custom.demo.loader import load_dataset
from mmm_custom.engine.catalog import build_catalog
from mmm_custom.engine.state import ConversationState

from mmm_custom.engine.render import jinja_renderer

render = jinja_renderer()


def demo_catalog(**settings):
    data = load_dataset()
    data["settings"] = {**data["settings"], **settings}
    return build_catalog(data)


def fill(value, source="keyword"):
    return {"value": value, "source": source, "confidence": 1.0}


class FakeJev:
    """Answers from a dict or a function of the questions."""

    def __init__(self, answers=None, status="ok"):
        self.answers, self.status, self.calls = answers or {}, status, []

    def ask(self, state, questions):
        from mmm_custom.engine.jev import JevResult

        self.calls.append((state, questions))
        if self.status != "ok":
            return JevResult(self.status, questions=questions, error="fake failure")
        answers = self.answers(questions) if callable(self.answers) else self.answers
        return JevResult("ok", {k: v for k, v in answers.items() if k in questions}, questions, "jev-test", 120, 7)


class FakeRepo:
    """In-memory stand-in for engine.repo.FrappeRepo."""

    def __init__(self, catalog, today=date(2026, 9, 28)):
        self._catalog, self._today = catalog, today
        self.states = {}
        self.prefill = {}
        self.schedules, self.promotions = [], []
        self.logs, self.signals = [], []
        self.consultant_rows, self.load, self.owners = [], {}, {}

    def catalog(self):
        return self._catalog

    def today(self):
        return self._today

    def load_state(self, event):
        if event.conversation_id in self.states:
            return copy.deepcopy(self.states[event.conversation_id])
        return ConversationState(conversation_id=event.conversation_id,
                                 contact_id=str(event.contact.get("id") or ""), slots=copy.deepcopy(self.prefill))

    def save_state(self, state):
        self.states[state.conversation_id] = copy.deepcopy(state)

    def open_schedules(self, course, branch, shift, today, limit):
        rows = [s for s in self.schedules if s["course"] == course and s["date"] >= today
                and (not branch or s["branch"] == branch) and (not shift or s["shift"].startswith(shift))]
        return sorted(rows, key=lambda s: s["date"])[:limit]

    def active_promotions(self, today):
        return list(self.promotions)

    def write_log(self, row):
        self.logs.append(row)

    def write_signal(self, row):
        self.signals.append(row)

    def consultants(self):
        return list(self.consultant_rows)

    def consultant_load(self):
        return dict(self.load)

    def lead_owner(self, lead):
        return self.owners.get(lead, "")


def schedule(course, branch, day, shift="Tối 17:00–21:00", weekdays="T3, T5, T7", seats=6):
    return {"course": course, "branch": branch, "date": day, "shift": shift, "weekdays": weekdays,
            "seats_left": seats}


def promo(title, kind="Percent", amount=10, courses=(), groups=(), branches=()):
    return {"title": title, "discount_type": kind, "discount_value": amount, "courses": list(courses),
            "course_groups": list(groups), "branches": list(branches)}


def demo_consultants():
    return [{"name": c["email"], "full_name": c["full_name"], "branch": c["branch"], "chatwoot_agent_id": i + 1,
             "active": 1, "handles_b2b": c["handles_b2b"], "level": c["level"]}
            for i, c in enumerate(load_dataset()["consultants"])]
