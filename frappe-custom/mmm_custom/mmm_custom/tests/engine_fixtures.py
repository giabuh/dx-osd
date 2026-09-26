"""Shared offline fixtures for the lead-engine tests: the demo catalog and in-memory fakes."""

import copy
import sys
from datetime import date
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import jinja2
import jinja2.sandbox

from mmm_custom.demo.loader import load_dataset
from mmm_custom.engine.catalog import build_catalog
from mmm_custom.engine.state import ConversationState

_ENV = jinja2.sandbox.SandboxedEnvironment(undefined=jinja2.DebugUndefined)


def render(template, context):
    return _ENV.from_string(template).render(context)


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
