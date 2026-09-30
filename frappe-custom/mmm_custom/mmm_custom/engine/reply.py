"""Turn a Decision into what the customer sees (D-050…D-054, D-072): paragraphs rendered from
templates with the context contract and the render guard, split under Messenger's limit, plus one set
of quick-reply buttons."""

from dataclasses import dataclass, field

from mmm_custom.engine.actions import run_action
from mmm_custom.engine.context import base_context, course_context
from mmm_custom.engine import enrol_flow, offers
from mmm_custom.engine.jev_questions import COURSE_FACT, COURSE_FAQ, STAFF_REPLY
from mmm_custom.engine.render import RenderError, condition, render_text
from mmm_custom.engine.slot_types import REGISTRY

MAX_MESSAGE = 2000  # Messenger text limit
MAX_BUTTONS = 13    # Messenger quick replies per message
MAX_TITLE = 20      # Messenger quick-reply title
MAX_FOLLOW_UPS = 3  # D-054
CONFIRM_YES, CONFIRM_NO = "Đúng ạ", "Không phải"

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
    ask: str = ""
    pending_skill: str = ""
    jev_extra: list = field(default_factory=list)
    hold: bool = False  # an action is mid-dialogue (a quiz question): ask no other slot this turn (D-104)
    skipped: list = field(default_factory=list)  # slots an action found nothing to ask for (no open class, D-121)

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


def compose(decision, state, catalog, render, data=None, today=None, extra=None, jev=None, jev_state=None):
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

    if decision.greet:  # later in the conversation a short greeting back, not the bot's introduction (D-109)
        say(settings["regreet_template"] if state.turns else settings["greeting_template"], ctx,
            "regreet" if state.turns else "greeting")
    if decision.declined:
        say(settings["quiz_decline_template"], ctx, "quiz_decline")
    if decision.fallback:
        say(settings["fallback_template"], ctx, "fallback")

    if decision.faq:  # the customer's own question about the course comes first (D-085)
        course = catalog.courses.get(decision.faq["course"])
        index = decision.faq["index"]
        if course and index < len(course.faqs):
            say(course.faqs[index].answer, {**ctx, "course": course_context(course, catalog)}, COURSE_FAQ)
            reply.variants.append({"skill": COURSE_FAQ, "variant": str(index)})
    elif decision.staff_reply:  # …or what staff once answered to the same question (D-114)
        reply_row = catalog.staff_reply(decision.staff_reply["name"])
        if reply_row:
            say(reply_row.reply, ctx, STAFF_REPLY)
            reply.variants.append({"skill": STAFF_REPLY, "variant": reply_row.name})
    elif decision.fact:  # …or the part of the course's own data it asks about (D-110)
        course = catalog.courses.get(decision.fact["course"])
        key = decision.fact["fact"]
        if course:
            say(settings[f"fact_{key}_template"], {**ctx, "course": course_context(course, catalog)}, COURSE_FACT)
            reply.variants.append({"skill": COURSE_FACT, "variant": key})

    action_buttons, follow_ups = [], []
    for key in decision.skills:
        skill = catalog.skills[key]
        try:
            action_ctx = {**ctx, "resumed": key == decision.resume, "unclear": key == decision.resume and decision.unclear,
                          "enrol_stop": decision.enrol_stop}
            out = run_action(skill, action_ctx, decision.slots, catalog, data, today, jev, jev_state)
        except Exception as e:
            reply.errors.append({"type": "action_error", "source": key, "detail": str(e)[:300]})
            out = {}
        if "_jev" in out:
            reply.jev_extra.append(out["_jev"])
            jev = None
        if out.get("_ask"):
            reply.ask, reply.pending_skill = reply.ask or out["_ask"], reply.pending_skill or key
            continue
        if out.get("_skip"):
            continue
        if out.get("_skip_slot"):
            reply.skipped.append(out["_skip_slot"])
        if out.get("_then_ask") and not reply.ask and decision.type != "handoff":
            reply.ask = out["_then_ask"]  # asked after this answer, not instead of it
        skill_ctx = {**ctx, **{k: v for k, v in out.items() if not k.startswith("_")}}
        template = choose_template(skill, skill_ctx, render)
        if template:
            say(template.text, skill_ctx, key)
            reply.variants.append({"skill": key, "variant": template.key})
        reply.hold = reply.hold or bool(out.get("_hold"))
        reply.attachments += out.get("_attachments", [])
        action_buttons = out.get("_buttons") or action_buttons  # one set of buttons: the last answer that has some
        follow_ups += [{"title": f.title, "action": FOLLOW_UP_ACTIONS[f.target_type](f.target)}
                       for f in skill.follow_ups if f.target_type in FOLLOW_UP_ACTIONS]

    if decision.voucher:  # level-test reward: syllabus of the recommended course, and a voucher code (D-106)
        say(settings["quiz_voucher_template"], {**ctx, "voucher": decision.voucher}, "quiz_voucher")

    if decision.type == "handoff":
        say(settings["handoff_template"], ctx, "handoff")

    confirm_buttons = []
    if decision.type == "confirm":
        c = decision.confirm
        template = settings["confirm_slot_template"] if c.get("kind") == "slot" else settings["confirm_skill_template"]
        say(template, {**ctx, "confirm": c}, "confirm")
        confirm_buttons = [{"title": CONFIRM_YES, "action": {"type": "confirm_yes", **c}},
                           {"title": CONFIRM_NO, "action": {"type": "confirm_no", **c}}]

    offer_buttons = []
    if decision.offer and not reply.ask and not reply.hold:
        say(settings["quiz_offer_template"], {**ctx, "quiz": offers.offer_context(decision.offer, decision.slots, catalog)},
            "quiz_offer")
        offer_buttons = offers.buttons(decision.offer)

    ask_buttons = []
    ask_key = reply.ask or ("" if reply.hold else decision.ask)
    if ask_key:
        slot = catalog.slot(ask_key)
        template = slot.ask_template
        if slot.type == "phone" and decision.phone_check and settings["phone_check_template"]:
            template = settings["phone_check_template"]
        elif slot.type == "phone" and settings["quiz_phone_template"] and (
                decision.quiz_done or (decision.slots.get("placement") or {}).get("source") == "quiz"):  # earns the reward
            template = settings["quiz_phone_template"]
        say(template, {**ctx, "phone_suspect": decision.phone_check}, f"slot:{slot.key}")
        if slot.type in REGISTRY:
            ask_buttons = REGISTRY[slot.type].buttons(slot, decision.slots, catalog)

    if decision.type != "handoff" and enrol_flow.phase(decision.slots, catalog) == enrol_flow.OPEN:
        follow_ups = []  # the registration dialogue asks one thing; other buttons would lead the customer away (D-121)
    for group in (confirm_buttons, offer_buttons, action_buttons, ask_buttons, follow_ups[:MAX_FOLLOW_UPS]):
        if group:
            add_buttons(reply, group)
            break
    reply.messages = split_messages(paragraphs)
    return reply
