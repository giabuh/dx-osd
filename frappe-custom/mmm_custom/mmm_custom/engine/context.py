"""The template context contract (D-050). Every template — skill answers, slot questions, greeting,
fallback, handoff and summary — gets exactly these keys; a skill's action adds schedules, promotions,
final_fee or recommendations for that skill only."""

from mmm_custom.engine.state import filled, value

# customer.* keys and the Bot Slot rows that feed them.
CUSTOMER_SLOTS = {"name": "customer_name", "learner": "learner", "learner_age": "learner_age", "shift": "preferred_shift"}


def brand_context(settings):
    return {"name": settings["brand_name"], "bot_name": settings["bot_name"], "you": settings["address_customer"],
            "me": settings["address_self"], "hotline": settings["hotline"], "zalo": settings["zalo"],
            "website": settings["website"], "signoff": settings["signoff"]}


def course_context(course, catalog):
    if not course:
        return {}
    return {"code": course.code, "name": course.name, "group": course.group, "fee": course.fee,
            "duration": course.duration, "audience": course.audience, "min_age": course.min_age,
            "max_age": course.max_age, "certificate": course.certificate, "image": course.image,
            "summary": course.summary, "syllabus": list(course.syllabus),
            "next_courses": [catalog.courses[c].name for c in course.next_courses if c in catalog.courses]}


def branch_context(branch):
    if not branch:
        return {}
    return {"name": branch.name, "address": branch.address, "hotline": branch.hotline, "map_url": branch.map_url,
            "area": branch.area}


def display(slot, raw, catalog):
    """A filled slot as a person reads it: option label, course name, or the raw value."""
    if slot.type == "choice" and slot.option(raw):
        return slot.option(raw).label
    if slot.type == "catalog" and slot.source == "course" and raw in catalog.courses:
        return catalog.courses[raw].name
    return str(raw)


def shown_slots(slots, catalog):
    return {s.key: display(s, value(slots, s.key), catalog) for s in catalog.slots if filled(slots, s.key)}


def base_context(slots, catalog, state):
    shown = shown_slots(slots, catalog)
    course_slot, branch_slot = catalog.slot_for("course"), catalog.slot_for("branch")
    course = catalog.courses.get(value(slots, course_slot.key)) if course_slot else None
    branch = catalog.branches.get(value(slots, branch_slot.key)) if branch_slot else None
    area = branch.area if branch else ((slots.get(branch_slot.key) or {}).get("parent", "") if branch_slot else "")
    customer = {key: shown.get(slot_key, "") for key, slot_key in CUSTOMER_SLOTS.items()}
    customer["is_returning"] = state.is_returning
    return {
        "brand": brand_context(catalog.settings), "customer": customer, "course": course_context(course, catalog),
        "branch": branch_context(branch), "area": area, "schedules": [], "promotions": [],
        "final_fee": course.fee if course else 0, "recommendations": [], "slots": shown,
        "missing": [s.label for s in catalog.slots if s.required and not filled(slots, s.key)],
    }
