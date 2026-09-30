"""decide(): the pure heart of a bot turn (D-025) — no I/O, offline-testable.

Given the conversation state, what the message was understood to say, and the catalog, return one
Decision: answer skill(s) (and ask the next slot), ask the next missing slot, hand off, or stay silent.
"""

import copy
from dataclasses import dataclass, field

from mmm_custom.engine.offers import BUTTON_ACTIONS, MAX_RESUMES, focus, paused_quiz, quiz_offer, subject
from mmm_custom.engine.state import filled, value

HANDOFF_REASONS = {
    "button": "Khách chọn gặp tư vấn viên",
    "skill": "Câu hỏi cần tư vấn viên xử lý",
    "wants_human": "Khách muốn gặp tư vấn viên",
    "hot": "Khách hot, sẵn sàng đăng ký",
    "required_filled": "Đã đủ thông tin bắt buộc",
    "stuck": "Bot chưa hiểu khách nhiều lượt liên tiếp",
}
IMMEDIATE = ("button", "wants_human", "skill")
# Why a person must answer, in the words a staff draft note uses (D-110); other reasons need no note.
STAFF_REASONS = {"wants_human": "muốn gặp người thật", "button": "khách chọn gặp tư vấn viên"}


@dataclass
class Decision:
    type: str                                   # answer | confirm | ask_slot | handoff | silent
    slots: dict = field(default_factory=dict)   # slots after this turn
    new_slots: list = field(default_factory=list)
    skills: list = field(default_factory=list)  # skill keys to answer, in reply order
    ask: str = ""                               # slot whose question ends the reply
    greet: bool = False
    fallback: bool = False
    handoff_reason: str = ""                    # button | skill | required_filled | stuck
    pending_skill: str = ""
    stuck_turns: int = 0
    reason: str = ""
    confirm: dict = field(default_factory=dict)
    ai: dict = field(default_factory=dict)
    close: bool = False
    faq: dict = field(default_factory=dict)     # course FAQ answered first (D-085)
    fact: dict = field(default_factory=dict)    # …or a part of the course's own data (D-110)
    staff_reply: dict = field(default_factory=dict)  # …or a reply staff once wrote (D-114), before a fact
    offer: str = ""                             # level quiz offered instead of the next slot question (D-106)
    declined: str = ""                          # level quiz the customer put off this turn
    resume: str = ""                            # level quiz asked again after the customer's side question (D-107)
    unclear: bool = False                       # …after a message that answered nothing (ask to pick a button)
    phone_check: str = ""                       # a phone number with a digit missing: ask to check it (D-107)
    quiz_done: str = ""                         # level quiz finished this turn: ask the phone next (pipeline)
    voucher: dict = field(default_factory=dict)  # level-test reward sent this turn (pipeline, D-106)

    @property
    def answered(self):
        """Something the customer asked is answered: a skill, the course's FAQ or data, or a staff reply."""
        return bool(self.skills or self.faq or self.fact or self.staff_reply)


FACT_LABELS = {"summary": "giới thiệu khóa", "syllabus": "nội dung học", "duration": "thời lượng", "audience": "đối tượng học",
               "certificate": "chứng chỉ", "next": "khóa học tiếp theo"}


def faq_question(faq, catalog):
    return catalog.courses[faq["course"]].faqs[faq["index"]].question


def fact_label(fact, catalog):
    return f"{FACT_LABELS.get(fact['fact'], fact['fact'])} khóa {catalog.courses[fact['course']].name}"


def slot_active(slot, slots):
    return not slot.depends_on or value(slots, slot.depends_on[0]) == slot.depends_on[1]


def required_filled(slots, catalog):
    return all(filled(slots, s.key) for s in catalog.slots if s.required and slot_active(s, slots))


def merge(slots, u, catalog):
    """Apply an Understanding to the slots; returns (slots, newly filled keys, other changed keys)."""
    out = copy.deepcopy(slots)
    changed = []
    for key, parent in u.parents.items():
        slot, entry = catalog.slot(key), out.setdefault(key, {})
        if slot and entry.get("parent") != parent:
            entry["parent"] = parent
            entry.pop("candidates", None)
            changed.append(key)
            if filled(out, key) and catalog.parent_of(slot, entry["value"]) != parent:
                entry.pop("value", None)  # D-029: a course outside the chosen group is dropped
    for key, candidates in u.ambiguous.items():
        if key not in u.fills:
            entry = out.setdefault(key, {})
            if u.focus == key and entry.get("value") in candidates:
                entry.pop("value", None)  # an explicit "not X, Y" must not leave X silently stored
            entry["candidates"] = list(candidates)
            changed.append(key)
    new = []
    for key, fill in u.fills.items():
        slot, entry = catalog.slot(key), out.setdefault(key, {})
        if entry.get("value") != fill["value"]:
            entry.update(fill)
            new.append(key)
        entry.pop("candidates", None)
        parent = catalog.parent_of(slot, fill["value"]) if slot else ""
        if parent:
            entry["parent"] = parent
    for key in u.skipped:
        out.setdefault(key, {})["skipped"] = 1
        changed.append(key)
    return out, new, changed


def pick_skills(state, u, slots, catalog):
    """Skills to answer now (capped, by sort_order) and the first one still waiting for a slot."""
    keys = list(dict.fromkeys(u.skills + ([state.pending_skill] if state.pending_skill else [])))
    ready, waiting = [], ""
    for key in keys:
        skill = catalog.skills.get(key)
        if not skill:
            continue
        missing = [p for p in skill.params if catalog.slot(p) and not filled(slots, p)]
        if missing and skill.missing_policy == "ask":
            waiting = waiting or key
            continue
        ready.append(skill)
    ready.sort(key=lambda s: s.order)
    return [s.key for s in ready[: int(catalog.settings["max_skills_per_reply"])]], waiting


def next_slot(slots, catalog, first=()):
    ordered = [catalog.slot(k) for k in first if catalog.slot(k)] + list(catalog.slots)
    for slot in ordered:
        entry = slots.get(slot.key) or {}
        if slot.on_demand and slot.key not in first:
            continue
        if filled(slots, slot.key) or not slot_active(slot, slots):
            continue
        if slot.key not in first and not slot.required and (entry.get("asked") or entry.get("skipped")):
            continue
        return slot.key
    return ""


def handoff_reason(u, skills, slots, stuck, catalog):
    floor = float(catalog.settings["handoff_noul"])
    if u.handoff:
        return "button"
    if u.wants_human >= floor:
        return "wants_human"
    if any(catalog.skills[k].action == "handoff" or catalog.skills[k].handoff_after for k in skills):
        return "skill"
    if u.hotness.get("value") == "hot" and u.hotness.get("confidence", 0) >= floor:
        return "hot"
    if required_filled(slots, catalog):
        return "required_filled"
    if stuck >= int(catalog.settings["max_stuck_turns"]):
        return "stuck"
    return ""


def decide(state, u, catalog, person_ok=False):
    """`person_ok` (D-111): answer even though a person wrote in this conversation (the assist wait ran out)."""
    keep = dict(slots=copy.deepcopy(state.slots), stuck_turns=state.stuck_turns, pending_skill=state.pending_skill)
    if state.status == "closed":
        return Decision("silent", **keep, reason="Hội thoại đã đóng")
    if state.consultant_replied and not person_ok:
        return Decision("silent", **keep, reason="Tư vấn viên đã nhắn khách, bot im lặng")
    if u.spam and not state.lead:
        return Decision("silent", **keep, close=True, reason=f"Tin nhắn rác ({u.spam:.2f}): bot dừng, không tạo Lead")

    slots, new, changed = merge(state.slots, u, catalog)
    skills, waiting = pick_skills(state, u, slots, catalog)
    faq = u.faq  # one answer from the course's knowledge: its FAQ, else a staff reply, else its data
    staff = {} if faq else u.staff_reply
    fact = {} if (faq or staff) else u.fact
    small_talk = u.greeting and not (new or changed or faq or staff or fact)
    if small_talk:
        skills = []  # "hihi" / "chào em" asks nothing: greet back and invite, never hand off (D-109)
    alone = [k for k in skills if catalog.skills[k].config.get("alone")]
    if alone:  # e.g. a company asking for a quote: no retail fee or course FAQ on top (D-099)
        skills, faq, staff, fact = alone, {}, {}, {}
    know = faq or staff or fact
    if staff:  # staff's own answer to this very topic replaces the bot's (D-114)
        topic = catalog.staff_reply(staff["name"]).topic
        skills = [k for k in skills if k != topic]
    if know:  # the course's own answer beats a generic template answer to the same question (D-085, D-110)
        skills = [k for k in skills if catalog.skills[k].action != "answer_template"]
    skills, squeezed = focus(skills, catalog)
    phone = next((s.key for s in catalog.slots if s.type == "phone"), "")
    if phone in u.fills or u.phone_suspect or u.gives_contact:  # their number, not a question about ours (D-107)
        skills = [k for k in skills if not catalog.skills[k].config.get("not_when_customer_gives_phone")]
    phone_check = u.phone_suspect if phone and not filled(slots, phone) else ""
    paused = paused_quiz(state.pending)
    resume = ""
    if (paused and paused not in skills and not u.declined and not u.handoff and not u.phone_suspect
            and state.status == "active" and int(state.pending.get("resumes") or 0) < MAX_RESUMES):
        resume = paused  # answer the side question, then the question the customer stopped at
        skills = skills + [paused]
    greet = (state.turns == 0 or small_talk) and not skills and not know
    side = [k for k in skills if k != resume]
    unclear = bool(resume) and not (new or changed or side or know or waiting)  # nothing but an unknown answer
    progress = bool(new or changed or skills or waiting or know or u.handoff or u.focus or u.confirm or u.rejected
                    or u.declined or u.phone_suspect)
    stuck = 0 if progress or greet else state.stuck_turns + 1
    common = dict(slots=slots, new_slots=new, skills=skills, pending_skill=waiting, stuck_turns=stuck, faq=faq, fact=fact, staff_reply=staff,
                  declined=u.declined, resume=resume, phone_check=phone_check, ai={k: v for k, v in (("intent", u.intent), ("hotness", u.hotness)) if v})
    answered = ", ".join(([f'"{faq_question(faq, catalog)}"'] if faq else []) +
                         ([fact_label(fact, catalog)] if fact else []) + (["câu trả lời NV"] if staff else []) +
                         [catalog.skills[k].title for k in side])

    if state.status == "handed_off":
        if small_talk:
            return Decision("answer", **common, greet=True, reason="Khách chào; chào lại, chờ tư vấn viên")
        if skills or know:
            return Decision("answer", **common, reason=f"Đã chuyển tư vấn viên; trả lời: {answered}")
        return Decision("silent", **common, reason="Đã chuyển tư vấn viên, chờ tư vấn viên nhắn")

    confirm = u.confirm
    if confirm.get("kind") == "skill" and (new or changed or skills or waiting or know):
        confirm = {}  # the turn already answers or asks something: a "did you mean…?" on top is noise
    why = "" if small_talk else handoff_reason(u, skills, slots, stuck, catalog)
    if why and (why in IMMEDIATE or not confirm):
        return Decision("handoff", **common, handoff_reason=why, reason=HANDOFF_REASONS[why])
    if confirm:
        reason = f"Xác nhận: {confirm['label']}" + (f"; trả lời: {answered}" if answered else "")
        return Decision("confirm", **common, confirm=confirm, greet=greet, reason=reason)

    if small_talk and state.turns and not resume:  # mid-conversation greeting: greet back, invite a course (D-109)
        course = catalog.slot_for("course")
        ask = course.key if course and not filled(slots, course.key) and slot_active(course, slots) else ""
        if ask:
            slots.setdefault(ask, {})["asked"] = 1
        return Decision("ask_slot" if ask else "answer", **common, ask=ask, greet=True,
                        reason="Khách chào; chào lại và mời chọn khóa" if ask else "Khách chào; chào lại và mời tư vấn tiếp")
    first = ([phone] if phone_check else []) + ([u.focus] if u.focus else []) + \
        (list(catalog.skills[waiting].params) if waiting else [])
    ask = next_slot(slots, catalog, first)
    later = not ask or not catalog.slot(ask).required or catalog.slot(ask).type == "phone"
    offer = "" if first or u.declined or not later else quiz_offer(state, u, slots, catalog, skills)
    if squeezed and not offer and squeezed not in state.offers and not any(
            catalog.skills[k].action in BUTTON_ACTIONS for k in skills):
        offer = squeezed  # asked for a test together with something else: answer first, then offer it
    if offer:  # the level test replaces an optional question or the phone one, which it earns (D-106)
        why_offer = ("khách hỏi cùng câu khác" if offer == squeezed else
                     "chưa rõ trình độ" if not filled(slots, "level") else "khách chưa chắc trình độ")
        offered = f"Mời làm bài test {subject(offer, catalog)} ({why_offer})"
        reason = f"Trả lời: {answered}; {offered[0].lower()}{offered[1:]}" if answered else offered
        return Decision("answer" if answered else "ask_slot", **common, greet=greet, offer=offer, reason=reason)
    reason = f"Trả lời: {answered}" if answered else ("Khách để sau bài test" if u.declined else "")
    if resume:  # the quiz holds the turn: no other question
        again = f"quay lại câu hỏi bài test {subject(resume, catalog)} đang dở"
        reason = f"{reason}; {again}" if reason else again[0].upper() + again[1:]
        return Decision("answer", **common, greet=greet, unclear=unclear, reason=reason)
    if ask:
        slots.setdefault(ask, {})["asked"] = 1
    label = catalog.slot(ask).label.lower() if ask else ""
    if phone_check:
        reason = f"{reason}; " if reason else ""
        reason += f"SĐT {phone_check} chưa đúng, nhờ khách kiểm tra lại"
    elif ask:
        reason = f"{reason}; hỏi tiếp {label}" if reason else f"Hỏi {label} (còn thiếu)"
    return Decision("answer" if answered else "ask_slot", **common, ask=ask, greet=greet,
                    fallback=not progress and not greet, reason=reason)
