"""Weekly plan from CRM data (D-125, spec 2026-10-01-weekly-plan-from-data-design.md): which courses the
autopilot posts about this week and why, and the facts a caption or banner may state.

Pure helpers (score, pick, assign_slots, title_for, build_facts, facts_lines, ensure_cta, unsupported_claims,
footer_text) are tested offline; load_candidates, plan_week and post_facts read the database."""

import re
from datetime import timedelta

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.comment_funnel import post_context
from mmm_custom.engine.render import vnd
from mmm_custom.engine.staff_replies import MONEY_RE, money_value
from mmm_custom.engine.text import PHONE_RE, fold

CLASS_DAYS, SOON_DAYS = 30, 14  # an open class starting within these days counts (more when soon)
RECENT_DAYS, REST_DAYS = 28, 7  # results window; a course posted this recently rests a week
MAX_LEAD_POINTS, MAX_REG_POINTS = 3, 4
PERCENT_RE = re.compile(r"\d+(?:[.,]\d+)?\s*%")
NEUTRAL_FOOTER = "Inbox fanpage để được tư vấn"


def _ddmm(d):
    return d.strftime("%d/%m")


def score(c, today):
    """(points, reasons) for one candidate course. Pure."""
    points, reasons = 0, []
    nxt = c.get("next_class")
    if nxt and (nxt.get("seats") or 0) > 0 and 0 <= (nxt["date"] - today).days <= CLASS_DAYS:
        points += 3 + (1 if (nxt["date"] - today).days <= SOON_DAYS else 0)
        reasons.append(f"lớp khai giảng {_ddmm(nxt['date'])} còn {nxt['seats']} chỗ")
    if c.get("promo"):
        points += 2
        reasons.append(f"đang có ưu đãi “{c['promo']}”")
    if c.get("leads"):
        points += min(c["leads"], MAX_LEAD_POINTS)
        reasons.append(f"bài gần đây ra {c['leads']} khách tiềm năng")
    if c.get("registrations"):
        points += min(2 * c["registrations"], MAX_REG_POINTS)
        reasons.append(f"{c['registrations']} học viên đăng ký từ bài gần đây")
    last = c.get("last_planned")
    if not last or (today - last).days > RECENT_DAYS:
        points += 1
        reasons.append("lâu chưa đăng")
    elif (today - last).days <= REST_DAYS:
        points -= 4
    return points, reasons


def pick(candidates, today, n=4):
    """The n best courses, at most one per course group until every group had its turn. Pure, deterministic."""
    ranked = []
    for c in candidates:
        points, reasons = score(c, today)
        ranked.append({**c, "points": points, "reasons": reasons})
    # equal points: the class that starts sooner is more urgent; then the code keeps it deterministic
    ranked.sort(key=lambda c: (-c["points"], (c["next_class"]["date"] - today).days if c.get("next_class") else 9999,
                               c["code"]))
    chosen, groups = [], set()
    for c in ranked:
        if len(chosen) < n and c["group"] not in groups:
            chosen.append(c)
            groups.add(c["group"])
    for c in ranked:
        if len(chosen) < n and c not in chosen:
            chosen.append(c)
    return chosen


def assign_slots(picked, offer_slot=3):
    """Picked courses in slot order; a course with a promotion takes the offer slot (Sunday FOMO angle)."""
    slots = list(picked)
    if len(slots) > offer_slot and not slots[offer_slot].get("promo"):
        promoted = next((i for i, c in enumerate(slots) if c.get("promo")), None)
        if promoted is not None:
            slots[promoted], slots[offer_slot] = slots[offer_slot], slots[promoted]
    return slots


def title_for(c):
    nxt = c.get("next_class")
    return f"{c['name']} – khai giảng {_ddmm(nxt['date'])}" if nxt else c["name"]


def build_facts(course_code, catalog, promotions, next_class):
    """What a post about this course may state, from CRM data only. Pure."""
    settings = catalog.settings
    ctx = post_context({"course": course_code}, catalog, promotions, None)
    return {"brand": settings.get("brand_name") or "", "hotline": settings.get("hotline") or "",
            "website": settings.get("website") or "", "branches": sorted(catalog.branches),
            "course": ctx.course, "promo": ctx.promo, "quiz_keyword": ctx.quiz_keyword,
            "next_class": next_class or None}


def facts_lines(facts):
    lines = []
    if facts.get("brand"):
        lines.append(f"Thương hiệu: {facts['brand']}")
    if facts.get("hotline"):
        lines.append(f"Hotline: {facts['hotline']}")
    if facts.get("website"):
        lines.append(f"Website: {facts['website']}")
    if facts.get("branches"):
        lines.append(f"Chi nhánh ({len(facts['branches'])}): {', '.join(facts['branches'])}")
    course = facts.get("course") or {}
    if course:
        lines.append(f"Khóa học: {course['name']}" + (f", học phí {vnd(course['fee'])}" if course.get("fee") else ""))
    promo = facts.get("promo") or {}
    if promo:
        lines.append(f"Ưu đãi đang áp dụng: {promo['title']}, học phí còn {vnd(promo['final_fee'])}")
    nxt = facts.get("next_class")
    if nxt:
        where = f" tại {nxt['branch']}" if nxt.get("branch") else ""
        lines.append(f"Lớp gần nhất: khai giảng {_ddmm(nxt['date'])}{where}")
    if facts.get("quiz_keyword"):
        lines.append(f"Bài test trình độ miễn phí: khách bình luận \"{facts['quiz_keyword']}\"")
    return lines


def hashtag(text):
    return "".join(w.capitalize() for w in fold(text).split())


def caption_rules(facts, course_name=""):
    """The caption prompt's data block: what the post may state, and nothing else. Pure."""
    lines = facts_lines(facts)
    tags = " ".join(f"#{t}" for t in dict.fromkeys(filter(None, (hashtag(facts.get("brand") or ""),
                                                                    hashtag(course_name)))))
    out = ""
    if lines:
        out += "- DỮ LIỆU CRM (chỉ dùng thông tin này):\n" + "".join(f"  • {x}\n" for x in lines)
        out += ("- Chỉ nêu học phí, ưu đãi, số điện thoại, địa chỉ, ngày khai giảng có trong DỮ LIỆU CRM; "
                "không bịa ưu đãi hay phần trăm giảm giá\n")
        if facts.get("branches"):
            out += "- Nhắc hotline và số chi nhánh, không cần liệt kê hết chi nhánh\n"
    else:
        out += "- Không nêu số điện thoại, địa chỉ hay ưu đãi cụ thể\n"
    if facts.get("quiz_keyword"):
        out += f"- Kêu gọi hành động: bình luận \"{facts['quiz_keyword']}\" để nhận bài test trình độ miễn phí, hoặc inbox fanpage\n"
    else:
        out += "- Kêu gọi hành động rõ ràng: nhắn tin/inbox fanpage để nhận tư vấn\n"
    if tags:
        out += f"- Kèm hashtag: {tags}\n"
    return out


def ensure_cta(content, keyword):
    """The level-test call to action at the end of a caption, unless it is already there."""
    content = content or ""
    if not keyword or fold(keyword) in fold(content):
        return content
    return f"{content.rstrip()}\n\n👉 Bình luận \"{keyword}\" để nhận bài test trình độ miễn phí!"


def _digits(text):
    return re.sub(r"\D", "", text or "")


def unsupported_claims(content, facts):
    """Amounts, percentages and phone numbers in a caption that the CRM data does not back. Pure."""
    data = "\n".join(facts_lines(facts))
    found = []
    phones_ok = {_digits(m.group(0)) for m in PHONE_RE.finditer(data)}
    for m in PHONE_RE.finditer(content or ""):
        if _digits(m.group(0)) not in phones_ok:
            found.append(f"số điện thoại {m.group(0).strip()}")
    text = PHONE_RE.sub(" ", content or "")
    amounts = {money_value(m) for m in MONEY_RE.finditer(PHONE_RE.sub(" ", data))}
    for m in MONEY_RE.finditer(text):
        if money_value(m) not in amounts:
            found.append(f"số tiền {m.group(0).strip()}")
    percents = {re.sub(r"\s", "", p) for p in PERCENT_RE.findall(data)}
    for p in PERCENT_RE.findall(text):
        if re.sub(r"\s", "", p) not in percents:
            found.append(f"mức giảm {p.strip()}")
    return found


def footer_text(facts):
    parts = []
    if facts.get("hotline"):
        parts.append(f"Hotline: {facts['hotline']}")
    if facts.get("website"):
        parts.append(re.sub(r"^https?://(www\.)?", "", facts["website"]).rstrip("/"))
    if facts.get("branches"):
        parts.append(f"{len(facts['branches'])} chi nhánh")
    return "  •  ".join(parts) or NEUTRAL_FOOTER


# ── Bench side ─────────────────────────────────────────────────────────────────────────────────────


def _next_classes(today):
    rows = frappe.get_all("Course Schedule", filters={"status": "Open", "start_date": [">=", today]},
                          fields=["course", "start_date", "seats", "branch"], order_by="start_date asc")
    out = {}
    for r in rows:
        if r.course not in out and (r.seats or 0) > 0:
            out[r.course] = {"date": r.start_date, "seats": r.seats, "branch": r.branch or ""}
    return out


def _post_stats(today):
    """{course: {"leads", "registrations", "last_planned"}} from Facebook Posts."""
    rows = frappe.get_all("Facebook Post", filters={"status": ["in", ["Posted", "Scheduled", "Pending Approval"]],
                                                    "course": ["is", "set"]},
                          fields=["course", "posted_at", "scheduled_time", "creation", "leads_count",
                                  "registrations_count"])
    since, out = today - timedelta(days=RECENT_DAYS), {}
    for r in rows:
        when = (r.posted_at or r.scheduled_time or r.creation).date()
        s = out.setdefault(r.course, {"leads": 0, "registrations": 0, "last_planned": None})
        s["last_planned"] = max(filter(None, (s["last_planned"], when)))
        if r.posted_at and r.posted_at.date() >= since:
            s["leads"] += r.leads_count or 0
            s["registrations"] += r.registrations_count or 0
    return out


def load_candidates(today, catalog, promotions):
    from mmm_custom.engine import actions, voucher
    from mmm_custom.engine.context import course_context

    classes, stats = _next_classes(today), _post_stats(today)
    out = []
    for course in catalog.courses.values():
        best, _ = voucher.best_promotion(promotions, course_context(course, catalog), "", actions.applicable,
                                         actions.discount)
        s = stats.get(course.code, {})
        out.append({"code": course.code, "name": course.name, "group": course.group,
                    "next_class": classes.get(course.code), "promo": best["title"] if best else "",
                    "leads": s.get("leads", 0), "registrations": s.get("registrations", 0),
                    "last_planned": s.get("last_planned")})
    return out


def _data(today):
    from mmm_custom.engine.repo import FrappeRepo, load_catalog

    return load_catalog(), FrappeRepo().active_promotions(today)


def plan_week(today, n=4, offer_slot=3):
    """The week's courses in slot order: [{code, name, title, reason, ...}]."""
    catalog, promotions = _data(today)
    picked = assign_slots(pick(load_candidates(today, catalog, promotions), today, n), offer_slot)
    return [{**c, "title": title_for(c), "reason": "; ".join(c["reasons"]) or "luân phiên khóa học"} for c in picked]


def post_facts(course_code):
    """build_facts on live data; {} when it cannot be read (the caller then states no contact details)."""
    if frappe is None:
        return {}
    try:
        today = frappe.utils.getdate()
        catalog, promotions = _data(today)
        return build_facts(course_code, catalog, promotions, _next_classes(today).get(course_code))
    except Exception:
        frappe.log_error(title="Marketing facts not read", message=str(course_code))
        return {}
