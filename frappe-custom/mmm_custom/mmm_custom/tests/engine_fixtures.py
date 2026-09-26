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


class FakeRepo:
    """In-memory stand-in for engine.repo.FrappeRepo."""

    def __init__(self, catalog, today=date(2026, 9, 28)):
        self._catalog, self._today = catalog, today
        self.states = {}
        self.prefill = {}
        self.schedules, self.promotions = [], []

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


def schedule(course, branch, day, shift="Tối 17:00–21:00", weekdays="T3, T5, T7", seats=6):
    return {"course": course, "branch": branch, "date": day, "shift": shift, "weekdays": weekdays,
            "seats_left": seats}


def promo(title, kind="Percent", amount=10, courses=(), groups=(), branches=()):
    return {"title": title, "discount_type": kind, "discount_value": amount, "courses": list(courses),
            "course_groups": list(groups), "branches": list(branches)}
