"""Turn a Decision into what the customer sees (D-050…D-054, D-072): paragraphs rendered from
templates with the context contract and the render guard, split under Messenger's limit, plus one set
of quick-reply buttons."""

from dataclasses import dataclass, field

from mmm_custom.engine.actions import run_action
from mmm_custom.engine.context import base_context
from mmm_custom.engine.render import RenderError, condition, render_text
from mmm_custom.engine.slot_types import REGISTRY

MAX_MESSAGE = 2000  # Messenger text limit
MAX_BUTTONS = 13    # Messenger quick replies per message
MAX_TITLE = 20      # Messenger quick-reply title
MAX_FOLLOW_UPS = 3  # D-054

FOLLOW_UP_ACTIONS = {
    "skill": lambda target: {"type": "skill", "skill": target},
    "slot": lambda target: {"type": "ask", "slot": target},
    "handoff": lambda target: {"type": "handoff"},
}


@dataclass
class Reply:
    messages: list = field(default_factory=list)
    buttons: list = field(default_factory=list)      # [{"title": str, "action": dict}]
    variants: list = field(default_factory=list)     # [{"skill": key, "variant": key}]
    attachments: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    def options(self):
        return {b["title"]: b["action"] for b in self.buttons}


def split_messages(paragraphs, limit=MAX_MESSAGE):
    """Join paragraphs with blank lines, starting a new message before `limit` is exceeded."""
    messages, current = [], ""
    for p in (p.strip() for p in paragraphs if p):
        if not p:
            continue
        while len(p) > limit:  # a single oversized paragraph is cut hard
            if current:
                messages.append(current)
                current = ""
            messages.append(p[:limit])
            p = p[limit:]
        candidate = f"{current}\n\n{p}" if current else p
        if len(candidate) > limit:
            messages.append(current)
            current = p
        else:
            current = candidate
    if current:
        messages.append(current)
    return messages


def add_buttons(reply, buttons):
    seen = {b["title"] for b in reply.buttons}
    for b in buttons:
        title = b["title"][:MAX_TITLE].strip()
        if title and title not in seen and len(reply.buttons) < MAX_BUTTONS:
            reply.buttons.append({"title": title, "action": b["action"]})
            seen.add(title)


def choose_template(skill, ctx, render):
    """First variant whose `when` holds; otherwise the variant without a condition."""
    default = None
    for t in skill.templates:
        if not t.when.strip():
            default = default or t
            continue
        try:
            if condition(t.when, ctx, render):
                return t
        except RenderError:
            continue
    return default


def compose(decision, state, catalog, render, data=None, today=None, extra=None):
    reply = Reply()
    if decision.type == "silent":
        return reply
    settings = catalog.settings
    ctx = {**base_context(decision.slots, catalog, state), **(extra or {})}
    paragraphs = []

    def fallback_text():
        try:
            return render_text(settings["fallback_template"], ctx, render) if settings["fallback_template"] else ""
        except RenderError:
            return ""

    def say(template, context, source):
        if not template:
            return
        try:
            paragraphs.append(render_text(template, context, render))
        except RenderError as e:  # D-051: never show template syntax
            reply.errors.append({"type": "render_error", "source": source, "detail": str(e)[:300]})
            text = fallback_text()
            if text and text not in paragraphs:
                paragraphs.append(text)

    if decision.greet:
        say(settings["greeting_template"], ctx, "greeting")
    if decision.fallback:
        say(settings["fallback_template"], ctx, "fallback")

    action_buttons, follow_ups = [], []
    for key in decision.skills:
        skill = catalog.skills[key]
        try:
            out = run_action(skill, ctx, decision.slots, catalog, data, today)
        except Exception as e:
            reply.errors.append({"type": "action_error", "source": key, "detail": str(e)[:300]})
            out = {}
        skill_ctx = {**ctx, **{k: v for k, v in out.items() if not k.startswith("_")}}
        template = choose_template(skill, skill_ctx, render)
        if template:
            say(template.text, skill_ctx, key)
            reply.variants.append({"skill": key, "variant": template.key})
        reply.attachments += out.get("_attachments", [])
        action_buttons += out.get("_buttons", [])
        follow_ups += [{"title": f.title, "action": FOLLOW_UP_ACTIONS[f.target_type](f.target)}
                       for f in skill.follow_ups if f.target_type in FOLLOW_UP_ACTIONS]

    if decision.type == "handoff":
        say(settings["handoff_template"], ctx, "handoff")

    ask_buttons = []
    if decision.ask:
        slot = catalog.slot(decision.ask)
        say(slot.ask_template, ctx, f"slot:{slot.key}")
        if slot.type in REGISTRY:
            ask_buttons = REGISTRY[slot.type].buttons(slot, decision.slots, catalog)

    for group in (action_buttons, ask_buttons, follow_ups[:MAX_FOLLOW_UPS]):  # D-072: one source of buttons
        if group:
            add_buttons(reply, group)
            break
    reply.messages = split_messages(paragraphs)
    return reply
