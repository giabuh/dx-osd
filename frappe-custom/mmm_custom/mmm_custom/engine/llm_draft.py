"""A Gemini draft for staff, for a question neither the course data nor the staff reply library answers (D-115).

Only staff see it, as a private note ("✍️ Nháp AI"), and only after two checks: Jev reads the draft against the
course's own data (answers the question, every claim is in the data, no promise the data does not make) and
code checks that every number in it (fees, dates, ages, sessions) appears in that data. Anything else is dropped
and staff see the plain "Jev chưa có tri thức" note instead. The bot never sends a draft to a customer, not even
when the assist wait runs out (copilot.answer sends the hold line)."""

import re

from mmm_custom.engine.context import base_context
from mmm_custom.engine.staff_replies import MONEY_RE, candidates, mask, money_value
from mmm_custom.engine.state import value

HEADER = "✍️ Nháp AI (Gemini) · đã đối chiếu dữ liệu khóa · kiểm tra trước khi gửi"
HOUR = 3600
SYSTEM = (
    "Bạn là tư vấn viên của một trung tâm đào tạo tin học ở Việt Nam, đang soạn NHÁP câu trả lời Messenger cho đồng "
    "nghiệp xem trước khi gửi khách. Xưng \"em\", gọi khách là \"anh/chị\" (phụ huynh: \"ba mẹ\"), mở đầu bằng \"Dạ\", "
    "lịch sự có \"ạ\", tối đa 3 câu, không emoji. CHỈ dùng thông tin trong DỮ LIỆU KHÓA HỌC được cung cấp; không bịa "
    "học phí, ngày khai giảng, ưu đãi, cam kết việc làm hay con số nào khác. Nếu dữ liệu không đủ để trả lời, viết "
    "một câu xin phép kiểm tra lại và hẹn báo khách sớm. Chỉ trả về nội dung tin nhắn."
)
MIN_ANSWERS, MIN_SUPPORTED, MAX_PROMISE = 0.8, 0.8, 0.3
NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")


def facts(state, catalog, schedules=(), promotions=()):
    """The course data the draft may use, as plain lines (what Gemini gets and what the checks compare with)."""
    ctx = base_context(state.slots, catalog, state)
    course = ctx["course"]
    lines = [f"Trung tâm: {ctx['brand']['name']}. Hotline: {ctx['brand']['hotline']}"]
    if course:
        lines += [f"Khóa: {course['name']} (nhóm {course['group']})", f"Học phí: {int(course['fee']):,}đ".replace(",", "."),
                  f"Thời lượng: {course['duration']}", f"Đối tượng: {course['audience']}"]
        if course["min_age"]:
            lines.append(f"Độ tuổi: {course['min_age']}–{course['max_age']} tuổi")
        if course["certificate"]:
            lines.append(f"Chứng chỉ: {course['certificate']}")
        if course["summary"]:
            lines.append(f"Giới thiệu: {course['summary']}")
        if course["syllabus"]:
            lines.append("Nội dung: " + "; ".join(course["syllabus"]))
        if course["next_courses"]:
            lines.append("Học tiếp: " + ", ".join(course["next_courses"]))
    for s in schedules:
        lines.append(f"Lớp khai giảng: {s.get('weekday', '')} {s.get('date')} · {s.get('shift', '')} · {s.get('branch', '')}")
    for p in promotions:
        lines.append(f"Ưu đãi: {p.get('title')}")
    if ctx["branch"]:
        lines.append(f"Chi nhánh khách chọn: {ctx['branch']['name']}, {ctx['branch']['address']}")
    return [line for line in lines if line.strip()]


def prompt(text, state, catalog, fact_lines, examples):
    history = "\n".join(f"{'Khách' if h.get('from') == 'customer' else 'Trung tâm'}: {mask(h.get('text', ''))}"
                        for h in state.history[-10:])
    style = "\n".join(f"- {e}" for e in examples) or "- (chưa có)"
    return (f"DỮ LIỆU KHÓA HỌC:\n" + "\n".join(fact_lines) + f"\n\nVÍ DỤ CÂU TRẢ LỜI CỦA NHÂN VIÊN (chỉ học giọng văn):\n"
            f"{style}\n\nHỘI THOẠI GẦN ĐÂY:\n{history or '(mới bắt đầu)'}\n\nTIN NHẮN MỚI CỦA KHÁCH:\n{mask(text)}\n\n"
            "Soạn câu trả lời:")


def numbers_ok(draft, fact_lines):
    """Every amount and number in the draft appears in the course data (amounts compared in đồng)."""
    data = "\n".join(fact_lines)
    amounts = {money_value(m) for m in MONEY_RE.finditer(data)}
    for m in MONEY_RE.finditer(draft):
        if money_value(m) not in amounts:
            return False
    plain = MONEY_RE.sub(" ", draft)
    known = set(NUMBER_RE.findall(MONEY_RE.sub(" ", data))) | {str(a) for a in amounts}
    return all(n in known for n in NUMBER_RE.findall(plain))


def checks(text, draft, fact_lines):
    """Jev's questions over the draft (one request)."""
    return {"state": {"customer_message": mask(text), "draft_reply": draft, "course_data": fact_lines},
            "questions": {
                "answers_question": {"type": "noul", "instructions": "Does `draft_reply` answer what `customer_message` asks?"},
                "supported": {"type": "noul", "instructions": "Is every fact stated in `draft_reply` (fees, dates, "
                              "content, conditions) found in `course_data`?"},
                "unapproved_promise": {"type": "noul", "instructions": "Does `draft_reply` promise something `course_data` "
                                       "does not offer (a discount, a job, a guarantee, a free item)?"}}}


def accepted(answers):
    def noul(key):
        try:
            return float((answers.get(key) or {}).get("noul"))
        except (TypeError, ValueError):
            return None

    a, s, p = noul("answers_question"), noul("supported"), noul("unapproved_promise")
    return None not in (a, s, p) and a >= MIN_ANSWERS and s >= MIN_SUPPORTED and p <= MAX_PROMISE


def allowed(state, settings, now):
    """Within the per-conversation budget (llm_drafts_per_hour) and not turned off."""
    if int(settings["llm_draft_disabled"] or 0):
        return False
    recent = [t for t in state.assist.get("llm_calls", []) if now - t < HOUR]
    return len(recent) < int(settings["llm_drafts_per_hour"])


def make(text, state, catalog, jev, generate, schedules=(), promotions=(), now=0.0):
    """(note or None, why). Records the call in state.assist["llm_calls"] (the caller saves the state)."""
    if not allowed(state, catalog.settings, now):
        return None, "budget"
    course_slot = catalog.slot_for("course")
    course = catalog.courses.get(value(state.slots, course_slot.key)) if course_slot else None
    fact_lines = facts(state, catalog, schedules, promotions)
    examples = [re.sub(r"\{\{.*?\}\}|\{%.*?%\}", "…", r.reply) for r in candidates(catalog, text, course, "", limit=4)]
    state.assist = {**state.assist, "llm_calls": [t for t in state.assist.get("llm_calls", []) if now - t < HOUR] + [now]}
    draft = generate(prompt(text, state, catalog, fact_lines, examples), SYSTEM)
    if not draft:
        return None, "no_draft"
    if not numbers_ok(draft, fact_lines):
        return None, "numbers"
    if jev is None:
        return None, "no_jev"
    check = checks(text, draft, fact_lines)
    result = jev.ask(check["state"], check["questions"])
    if result.status != "ok" or not accepted(result.answers):
        return None, "jev_rejected"
    return f"{HEADER}\n\n{draft}", "ok"
