"""Action registry (D-049): what a Bot Skill computes before its template renders. All lookups and
arithmetic are code here, never Jev (D-003). A new action = one function decorated with
@action("name") + the Select option in catalog_rules.ACTION_TYPES / the Bot Skill DocType.

An action returns extra template context; keys starting with "_" are instructions for the composer
(`_attachments`, `_buttons`), not template data."""

from dataclasses import dataclass

from mmm_custom.engine.context import CUSTOMER_SLOTS, branch_context
from mmm_custom.engine.advisor import advisor_questions, score_courses
from mmm_custom.engine.render import date_vi, vnd
from mmm_custom.engine.state import filled, value

ACTIONS = {}


def action(name):
    def register(fn):
        ACTIONS[name] = fn
        return fn
    return register


@dataclass
class ActionInput:
    skill: object
    ctx: dict
    slots: dict
    catalog: object
    data: object
    today: object
    jev: object = None
    jev_state: dict = None


def run_action(skill, ctx, slots, catalog, data, today, jev=None, jev_state=None):
    fn = ACTIONS.get(skill.action)
    return fn(ActionInput(skill, ctx, slots, catalog, data, today, jev, jev_state)) if fn else {}


@action("answer_template")
def answer_template(a):
    return {}


@action("handoff")
def handoff(a):
    return {}  # decide() hands the conversation off after this answer (D-058)


def find_schedules(data, ctx, today, limit):
    """Next open classes for the context's course; widen from branch + shift to anywhere when nothing
    matches. Also used for the handoff summary's next-step line (Task 6)."""
    course = ctx["course"]
    if not course:
        return []
    branch, shift = ctx["branch"].get("name"), ctx["customer"]["shift"] or None
    for b, s in dict.fromkeys(((branch, shift), (branch, None), (None, shift), (None, None))):
        rows = data.open_schedules(course["code"], b, s, today, limit)
        if rows:
            return rows
    return []


@action("schedule_lookup")
def schedule_lookup(a):
    return {"schedules": find_schedules(a.data, a.ctx, a.today, int(a.skill.config.get("limit", 3)))}


def _short_date(day):
    """date → "T3 06/10" (Messenger buttons are at most 20 characters)."""
    from datetime import date

    if isinstance(day, str):
        day = date.fromisoformat(day[:10])
    weekday = "CN" if day.weekday() == 6 else f"T{day.weekday() + 2}"
    return f"{weekday} {day:%d/%m}"


@action("trial_offer")
def trial_offer(a):
    """Free trial (D-102): the next open classes of the course as buttons; a tap fills the slot named in
    `action_config.slot` with a readable booking and answers the skill `action_config.skill`."""
    cfg, course = a.skill.config, a.ctx["course"]
    schedules = find_schedules(a.data, a.ctx, a.today, int(cfg.get("limit", 3))) if course else []
    buttons = []
    for s in schedules:
        shift = str(s.get("shift") or "").split(" ")[0]
        booking = " · ".join(x for x in (course["name"], date_vi(s["date"]), str(s.get("shift") or ""), s.get("branch") or "") if x)
        buttons.append({"title": f"{_short_date(s['date'])} {shift}".strip()[:20],
                        "action": {"type": "slot", "slot": cfg.get("slot", "trial_class"), "value": booking,
                                   "skill": cfg.get("skill", "")}})
    return {"schedules": schedules, "_buttons": buttons}


@action("book_trial")
def book_trial(a):
    """The booked trial for the confirmation template; the CRM Task is created by the pipeline (effects)."""
    return {"trial": value(a.slots, a.skill.config.get("slot", "trial_class")) or ""}


def applicable(promo, course, branch):
    """Empty course / group / branch lists on a promotion mean "all"."""
    return ((not promo["courses"] or course["code"] in promo["courses"])
            and (not promo["course_groups"] or course["group"] in promo["course_groups"])
            and (not promo["branches"] or branch in promo["branches"]))


def discount(promo, fee):
    if promo["discount_type"] == "Percent":
        return fee * float(promo["discount_value"]) / 100
    return float(promo["discount_value"])


def _label(promo):
    if promo["discount_type"] == "Percent":
        return f"{float(promo['discount_value']):g}%"
    return vnd(promo["discount_value"])


@action("fee_quote")
def fee_quote(a):
    """Listed fee, every promotion that applies, and the final fee after the single best one."""
    course = a.ctx["course"]
    if not course:
        return {}
    promos = [p for p in a.data.active_promotions(a.today) if applicable(p, course, a.ctx["branch"].get("name"))]
    best = max((discount(p, course["fee"]) for p in promos), default=0)
    return {"promotions": [{"title": p["title"], "discount": _label(p)} for p in promos],
            "final_fee": max(course["fee"] - best, 0)}


@action("branch_info")
def branch_info(a):
    area = a.ctx["area"]
    branches = a.catalog.branches_in(area) if area else list(a.catalog.branches.values())
    return {"branches": [branch_context(b) for b in branches]}


@action("send_media")
def send_media(a):
    media = a.skill.media or a.ctx["course"].get("image") or ""
    return {"_attachments": [media]} if media else {}


@action("recommend_courses")
def recommend_courses(a):
    """Course advisor: data filters from action_config (D-071), then Jev fit scoring of the shortlist
    with one extra call (D-055); below the floor it asks goal/level instead."""
    cfg, settings = a.skill.config, a.catalog.settings
    learner = value(a.slots, CUSTOMER_SLOTS["learner"])
    age = value(a.slots, CUSTOMER_SLOTS["learner_age"])
    audiences = [cfg["audience"]] if cfg.get("audience") else list((cfg.get("audience_by_learner") or {}).get(learner or "", []))
    course_slot = a.catalog.slot_for("course")
    group = (a.slots.get(course_slot.key) or {}).get("parent", "") if course_slot else ""
    candidates = [c for c in a.catalog.courses.values()
                  if (not audiences or c.audience in audiences)
                  and (not age or (c.min_age or 0) <= int(age) <= (c.max_age or 200))
                  and (not group or c.group == group)]
    top, out, scores = int(cfg.get("top", 3)), {}, {}
    picked = candidates[:top]
    if a.jev is not None and len(candidates) > 1:
        shortlist = candidates[: int(settings["advisor_shortlist"])]
        result = a.jev.ask(a.jev_state or {}, advisor_questions(shortlist))
        out["_jev"] = result.log()
        ranked = score_courses(shortlist, result.answers, settings) if result.status == "ok" else []
        if ranked and ranked[0][1] < float(settings["advisor_floor"]):
            ask = next((k for k in ("goal", "level") if a.catalog.slot(k) and not filled(a.slots, k)), "")
            if ask:
                return {**out, "_ask": ask}
        if ranked:
            picked, scores = [c for c, _ in ranked[:top]], dict((c.code, s) for c, s in ranked)
    buttons = [{"title": c.button, "action": {"type": "slot", "slot": course_slot.key, "value": c.code}}
               for c in picked] if course_slot else []
    out.update(recommendations=[{"course": c.name, "code": c.code, "fee": c.fee, "score": scores.get(c.code)}
                                for c in picked], _buttons=buttons)
    return out
