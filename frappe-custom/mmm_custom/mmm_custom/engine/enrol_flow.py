"""Registration dialogue (D-121). Pure, no I/O.

A customer who wants to register is led by the bot before any consultant is involved: pick a class (buttons, or
"let the consultant choose"), then leave a phone number; only then is the conversation handed off, with the draft
registration (D-118). When a message leaves the dialogue, Jev reads which way (`enrol_step`): a side question is
answered and the dialogue resumes, "later" or "no" ends it without a handoff, "no phone" or "any class" skips that
step, and a request for a person hands off at once (wants_human).

The dialogue's state lives on the class slot entry: `slots[<class slot>]["flow"]` = open | done | stopped.
"""

from mmm_custom.engine.state import filled

OPEN, DONE, STOPPED = "open", "done", "stopped"
STEP = "enrol_step"  # Jev question key
ANSWER, QUESTION, ANY_CLASS, NO_PHONE, LATER, CANCEL = "answer", "question", "any_class", "no_phone", "later", "cancel"
STEPS = {
    ANSWER: "Answers the bot's registration question: picks a class, gives a phone number, or simply agrees",
    QUESTION: "Asks something else first (fee, schedule, address, content, promotion) but still wants to register",
    ANY_CLASS: "Does not pick a class and wants the consultant to suggest or arrange one",
    NO_PHONE: "Does not want to give a phone number, or prefers to keep chatting here",
    LATER: "Is not ready now: wants to think it over, ask family, or register later",
    CANCEL: "No longer wants to register, or declines",
}
STOPS = (LATER, CANCEL)
ANY_CLASS_TITLE = "Nhờ tư vấn chọn lớp"


def skill_key(catalog):
    """The skill that runs the dialogue (action `enrol`), or ""."""
    skills = sorted((s for s in catalog.skills.values() if s.action == "enrol"), key=lambda s: s.order)
    return skills[0].key if skills else ""


def class_slot(catalog):
    key = skill_key(catalog)
    return catalog.skills[key].config.get("slot", "enrol_class") if key else ""


def phone_slot(catalog):
    return next((s.key for s in catalog.slots if s.type == "phone"), "")


def phase(slots, catalog):
    return ((slots or {}).get(class_slot(catalog)) or {}).get("flow", "")


def is_open(state, catalog):
    """The bot is leading this conversation through a registration."""
    return state.status == "active" and bool(skill_key(catalog)) and phase(state.slots, catalog) == OPEN


def _set(slots, catalog, flow):
    slots.setdefault(class_slot(catalog), {})["flow"] = flow


def start(slots, catalog):
    """Open the dialogue; steps skipped in an earlier, ended one are asked again."""
    _set(slots, catalog, OPEN)
    for key in (class_slot(catalog), phone_slot(catalog)):
        if key in slots:
            slots[key].pop("skipped", None)


def finish(slots, catalog):
    _set(slots, catalog, DONE)


def skip(slots, key):
    if key:
        slots.setdefault(key, {})["skipped"] = 1


def _todo(slots, key):
    return bool(key) and not filled(slots, key) and not (slots.get(key) or {}).get("skipped")


def next_step(slots, catalog):
    """"class", "phone", or "" once both are answered or skipped."""
    if _todo(slots, class_slot(catalog)):
        return "class"
    if _todo(slots, phone_slot(catalog)):
        return "phone"
    return ""


def apply_step(step, slots, catalog):
    """Jev's reading of a message inside the dialogue. Skips a step or ends the dialogue; returns LATER / CANCEL
    when it ended, else ""."""
    if step in STOPS:
        _set(slots, catalog, STOPPED)
        return step
    if step == ANY_CLASS:
        skip(slots, class_slot(catalog))
    elif step == NO_PHONE:
        skip(slots, phone_slot(catalog))
    return ""
