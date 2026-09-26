"""Turn a Decision into the messages and quick-reply buttons the customer sees."""

from dataclasses import dataclass, field

from mmm_custom.engine.slot_types import REGISTRY

MAX_MESSAGE = 2000  # Messenger text limit
MAX_BUTTONS = 13    # Messenger quick replies per message
MAX_TITLE = 20      # Messenger quick-reply title


@dataclass
class Reply:
    messages: list = field(default_factory=list)
    buttons: list = field(default_factory=list)      # [{"title": str, "action": dict}]
    variants: list = field(default_factory=list)     # [{"skill": key, "variant": key}]
    attachments: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    def options(self):
        return {b["title"]: b["action"] for b in self.buttons}


def brand_context(settings):
    return {"name": settings["brand_name"], "bot_name": settings["bot_name"], "you": settings["address_customer"],
            "me": settings["address_self"], "hotline": settings["hotline"], "zalo": settings["zalo"],
            "website": settings["website"], "signoff": settings["signoff"]}


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


def compose(decision, state, catalog, render):
    reply = Reply()
    if decision.type == "silent":
        return reply
    settings = catalog.settings
    ctx = {"brand": brand_context(settings)}
    paragraphs = []
    if decision.greet and settings["greeting_template"]:
        paragraphs.append(render(settings["greeting_template"], ctx))
    if decision.fallback and settings["fallback_template"]:
        paragraphs.append(render(settings["fallback_template"], ctx))
    if decision.ask:
        slot = catalog.slot(decision.ask)
        paragraphs.append(render(slot.ask_template, ctx))
        if slot.type in REGISTRY:
            add_buttons(reply, REGISTRY[slot.type].buttons(slot, decision.slots, catalog))
    reply.messages = split_messages(paragraphs)
    return reply
