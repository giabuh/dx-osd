"""Proactive level-test offer (D-106). Pure, no I/O.

Once the bot knows which course (or course group) the customer wants but not their level, it offers the
level quiz of that course instead of asking the next slot: "làm thử bài test Excel 5 câu…" with the buttons
[Làm bài test] [Để sau]. Each quiz is offered at most once per conversation; `state.offers` remembers
{skill: offered | declined | started | reminded | done | rewarded}.
"""

from mmm_custom.engine import quiz
from mmm_custom.engine.state import filled, value

OFFERED, DECLINED, STARTED, DONE, REMINDED, REWARDED = "offered", "declined", "started", "done", "reminded", "rewarded"
LEVEL_UNSURE = "level_unsure"  # Jev noul, asked only when an offer is possible
UNSURE_FLOOR = 0.6
START_TITLE, LATER_TITLE = "Làm bài test", "Để sau"
BUTTON_ACTIONS = ("trial_offer", "book_trial", "recommend_courses", "level_quiz", "enrol")  # answers that bring their own buttons
MAX_RESUMES = 2  # a customer who keeps asking other things is let go; the reminder job may bring them back


def paused_quiz(pending):
    """The quiz whose answer buttons the bot is waiting on, or ""."""
    actions = list(((pending or {}).get("options") or {}).values())
    if actions and all(a.get("type") == "slot" and a.get("slot") == "quiz_progress" for a in actions):
        return actions[0].get("skill") or ""
    return ""


def focus(skills, catalog):
    """One focus per reply (D-107): one course list, and no quiz squeezed between other answers.
    Returns (skills, quiz dropped)."""
    out, seen, dropped = [], set(), ""
    for key in skills:
        action = catalog.skills[key].action
        if action == "recommend_courses" and action in seen:
            continue
        seen.add(action)
        out.append(key)
    quizzes = [k for k in out if catalog.skills[k].action == "level_quiz"]
    if quizzes and len(out) > len(quizzes):
        dropped = quizzes[0]
        out = [k for k in out if k not in quizzes]
    return out, dropped


def wanted_course(slots, catalog):
    """(course code, course group) the customer is after, from the course slot (value or chosen group)."""
    slot = catalog.slot_for("course")
    if not slot:
        return "", ""
    entry = slots.get(slot.key) or {}
    course = catalog.courses.get(entry.get("value"))
    return (course.code, course.group) if course else ("", entry.get("parent") or "")


def available(state, slots, catalog):
    """The quiz that could be offered in this conversation (never offered before), or ""."""
    if state.status != "active" or state.consultant_replied or filled(slots, "placement"):
        return ""
    course, group = wanted_course(slots, catalog)
    key = quiz.quiz_for(catalog.skills, course, group) if course or group else ""
    return key if key and key not in state.offers else ""


def quiz_offer(state, u, slots, catalog, skills=()):
    """The quiz to offer this turn, or "". Not on the first turn, not while a quiz is being answered, and
    when the level is already known only if Jev reads the customer as unsure of it."""
    if state.turns < 1 or any(catalog.skills[k].action in BUTTON_ACTIONS for k in skills if k in catalog.skills):
        return ""  # not while a quiz runs, and never over another answer's buttons (a trial date, a course)
    key = available(state, slots, catalog)
    if not key:
        return ""
    if filled(slots, "level") and u.level_unsure < UNSURE_FLOOR:
        return ""
    return key


def subject(key, catalog):
    skill = catalog.skills.get(key)
    return (skill.config.get("subject") or skill.title) if skill else ""


def offer_context(key, slots, catalog):
    """`quiz` for the offer template: subject and how many questions this customer will get."""
    cfg = catalog.skills[key].config
    return {"subject": subject(key, catalog), "total": quiz.limit(cfg, value(slots, "goal") or "")}


def buttons(key):
    return [{"title": START_TITLE, "action": {"type": "skill", "skill": key}},
            {"title": LATER_TITLE, "action": {"type": "offer_decline", "skill": key}}]


def track(offers, decision, catalog, declined=""):
    """The conversation's offers after this turn (a new dict)."""
    out = dict(offers or {})
    if decision.offer:
        out[decision.offer] = OFFERED
    if declined:
        out[declined] = DECLINED
    for key in decision.skills:
        skill = catalog.skills.get(key)
        if not skill or skill.action != "level_quiz":
            continue
        answers = quiz.progress(value(decision.slots, skill.config.get("slot", "quiz_progress")), key)
        done = quiz.result(skill.config, answers, value(decision.slots, "goal") or "") is not None
        if out.get(key) != REWARDED:
            out[key] = DONE if done else (out.get(key) if out.get(key) == REMINDED else STARTED)
    if decision.voucher.get("quiz"):
        out[decision.voucher["quiz"]] = REWARDED
    return out


def attempt_changes(before, after, decision, catalog):
    """What changed for the Quiz Attempt rows this turn: [{quiz, status?, <field>: value, <x>_at: True}].
    `<x>_at: True` means "now" (the repo stamps it)."""
    out = []
    for key, now in after.items():
        was = (before or {}).get(key)
        if now == was:
            continue
        row = {"quiz": key}
        if now == OFFERED:
            row.update(status=OFFERED, offered_at=True)
        elif now == DECLINED:
            row.update(status=DECLINED)
        elif now == STARTED and was != REMINDED:
            row.update(status=STARTED, started_at=True)
        if now in (DONE, REWARDED) and was not in (DONE, REWARDED):
            skill = catalog.skills[key]
            answers = quiz.progress(value(decision.slots, skill.config.get("slot", "quiz_progress")), key)
            res = quiz.result(skill.config, answers, value(decision.slots, "goal") or "") or {}
            row.update(status=DONE, finished_at=True, score=res.get("score", 0), total=res.get("total", 0),
                       level=res.get("level", ""), missed=", ".join(res.get("missed", [])))
            if was is None:
                row["started_at"] = True
        if now == REWARDED:
            row.update(phone_after=1, voucher_code=decision.voucher.get("code", ""))
        if len(row) > 1:
            out.append(row)
    return out
