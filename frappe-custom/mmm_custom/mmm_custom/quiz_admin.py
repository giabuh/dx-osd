"""Level tests on the manager screens (/crm/admin/quizzes, D-106): list, edit and add the level quizzes
(Bot Skills with action `level_quiz`), and how many customers each one moves along: offered → took it →
finished → left a phone → enrolled. Saving checks the quiz (engine.quiz.validate) and the house tone of
its messages (engine.tone). The pure helpers are tested offline."""

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

import json

from mmm_custom.desk import can_open_bot
from mmm_custom.engine import quiz, tone
from mmm_custom.engine.text import fold

whitelist = frappe.whitelist if frappe else (lambda **kw: (lambda fn: fn))

PERIODS = (7, 30, 90, 365)
STAGES = (("offered", "Được mời"), ("started", "Làm bài"), ("done", "Làm xong"), ("phone", "Để lại SĐT"),
          ("enrolled", "Ghi danh"))
VARIANTS = (("start", "Câu mở đầu (câu 1)"), ("default", "Các câu tiếp theo"), ("result", "Báo kết quả"))
DEFAULT_TEMPLATES = {
    "start": "Dạ {{ brand.me }} gửi {{ brand.you }} bài test {{ quiz.subject }} nhỏ {{ quiz.total }} câu nhé ạ 😊 "
             "{{ brand.you | capitalize }} cứ bấm chọn đáp án là được ạ.\nCâu 1/{{ quiz.total }}: {{ quiz.question }}",
    "default": "Dạ {% if quiz.last_correct %}chính xác rồi ạ 👏 {% elif quiz.last_correct == false %}câu vừa rồi hơi khó, "
               "không sao đâu ạ. {% endif %}Câu {{ quiz.step }}/{{ quiz.total }} ạ: {{ quiz.question }}",
    "result": "Dạ {{ brand.you }} làm đúng {{ quiz.score }}/{{ quiz.total }} câu ạ. Trình độ hiện tại của {{ brand.you }} là "
              "{{ quiz.level_label }}, {{ brand.me }} gợi ý khóa {{ quiz.course_name }} ({{ quiz.course_fee | vnd }}) ạ."
              "{% if quiz.trials %} {{ brand.me | capitalize }} giữ sẵn một buổi học thử miễn phí, {{ brand.you }} chọn "
              "ngày bên dưới nhé ạ.{% endif %}",
}
WHEN = {"start": "not quiz.done and quiz.step == 1", "default": "", "result": "quiz.done"}


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _texts(values):
    return [str(v).strip() for v in values or [] if str(v).strip()]


def normalize(config):
    """A quiz configuration from the editor, cleaned: trimmed text, ints, empty options dropped. Pure."""
    mode = config.get("mode") if config.get("mode") in quiz.MODES else "test"
    questions = []
    for q in config.get("questions") or []:
        options = [str(o).strip() for o in q.get("options") or []]
        keep = [i for i, o in enumerate(options) if o]
        row = {"q": str(q.get("q") or "").strip(), "options": [options[i] for i in keep]}
        if mode == "test":
            answer = _int(q.get("answer"), -1)
            row["answer"] = keep.index(answer) if answer in keep else -1
        else:
            points = list(q.get("points") or [])
            row["points"] = [_int(points[i]) if i < len(points) else 0 for i in keep]
        for key in ("level", "topic"):
            if str(q.get(key) or "").strip():
                row[key] = str(q[key]).strip()
        if _texts(q.get("goals")):
            row["goals"] = _texts(q.get("goals"))
        questions.append(row)
    bands = sorted(({"max": _int(b.get("max")), "level": str(b.get("level") or ""), "course": str(b.get("course") or "")}
                    for b in config.get("bands") or []), key=lambda b: b["max"])
    out = {"slot": config.get("slot") or "quiz_progress", "subject": str(config.get("subject") or "").strip(),
           "mode": mode, "courses": _texts(config.get("courses")), "groups": _texts(config.get("groups")),
           "max_questions": max(_int(config.get("max_questions"), len(questions)), 1), "questions": questions,
           "bands": bands}
    if mode == "test" and _int(config.get("stop_after_wrong")):
        out["stop_after_wrong"] = _int(config.get("stop_after_wrong"))
    return out


def problems(config, templates, course_codes=(), levels=()):
    """Everything a manager must fix before saving ([] when fine). Pure."""
    errors = []
    if not config["subject"]:
        errors.append("Nhập tên môn của bài test (ví dụ Excel).")
    if not config["courses"] and not config["groups"]:
        errors.append("Chọn ít nhất một khóa hoặc nhóm khóa để bot biết lúc nào mời bài test này.")
    errors += quiz.validate(config, course_codes, levels)
    labels = dict(VARIANTS)
    for key, text in (templates or {}).items():
        errors += [f"{labels.get(key, key)}: {p}" for p in tone.problems(text or "")]
    return errors


def new_key(subject, existing):
    """"Tin học cho bé" → "tin_hoc_cho_be_quiz", unique among `existing`. Pure."""
    base = "_".join(fold(subject).split())[:30].strip("_") or "level"
    key, n = f"{base}_quiz", 2
    while key in existing:
        key, n = f"{base}_quiz_{n}", n + 1
    return key


def funnel(attempts, converted_leads):
    """Per quiz: [{stage, label, count}] from Quiz Attempt rows. Pure."""
    out = {}
    for row in attempts:
        counts = out.setdefault(row["quiz"], {key: 0 for key, _ in STAGES} | {"declined": 0, "reminded": 0,
                                                                                    "recovered": 0})
        counts["offered"] += bool(row.get("offered_at"))
        counts["declined"] += row.get("status") == "declined"
        counts["started"] += bool(row.get("started_at"))
        counts["done"] += row.get("status") == "done"
        counts["phone"] += bool(row.get("phone_after"))
        counts["enrolled"] += bool(row.get("lead") and row["lead"] in converted_leads)
        counts["reminded"] += bool(row.get("reminded_at"))
        counts["recovered"] += bool(row.get("reminded_at")) and row.get("status") == "done"
    return out


def _require_access():
    if not can_open_bot():
        frappe.throw("Bạn không có quyền quản trị bot.", frappe.PermissionError)


def _choices():
    levels = frappe.get_all("Bot Slot Option", filters={"parent": "level", "parenttype": "Bot Slot"},
                            fields=["value", "label"], order_by="idx asc")
    goals = frappe.get_all("Bot Slot Option", filters={"parent": "goal", "parenttype": "Bot Slot"},
                           fields=["value", "label"], order_by="idx asc")
    courses = frappe.get_all("CRM Product", filters={"disabled": 0}, fields=["name as code", "product_name as name",
                                                                           "course_group as group"], order_by="name asc")
    groups = frappe.get_all("Course Group", pluck="name", order_by="sort_order asc")
    return {"levels": levels, "goals": goals, "courses": courses, "groups": groups}


def _quiz_row(doc):
    templates = {t.variant_key: t.template for t in doc.templates}
    return {"key": doc.name, "title": doc.title, "active": bool(doc.active), "aliases": doc.aliases or "",
            "config": json.loads(doc.action_config or "{}"),
            "templates": {key: templates.get(key, "") for key, _ in VARIANTS}}


@whitelist()
def quizzes():
    _require_access()
    names = frappe.get_all("Bot Skill", filters={"action_type": "level_quiz"}, pluck="name", order_by="sort_order asc")
    return {"quizzes": [_quiz_row(frappe.get_doc("Bot Skill", n)) for n in names], "variants": VARIANTS,
            "defaults": DEFAULT_TEMPLATES, **_choices()}


@whitelist(methods=["POST"])
def save_quiz(skill="", title="", aliases="", active=1, config=None, templates=None):
    """Create or update one level quiz (a Bot Skill with action level_quiz)."""
    _require_access()
    config = normalize(frappe.parse_json(config) if isinstance(config, str) else (config or {}))
    templates = frappe.parse_json(templates) if isinstance(templates, str) else (templates or {})
    templates = {key: str(templates.get(key) or "").strip() or DEFAULT_TEMPLATES[key] for key, _ in VARIANTS}
    choices = _choices()
    errors = problems(config, templates, [c.code for c in choices["courses"]], [lv.value for lv in choices["levels"]])
    if errors:
        frappe.throw("\n".join(errors), title="Bài test chưa lưu được")
    if skill:
        doc = frappe.get_doc("Bot Skill", skill)
        if doc.action_type != "level_quiz":
            frappe.throw("Đây không phải bài test trình độ.")
    else:
        existing = set(frappe.get_all("Bot Skill", pluck="name"))
        doc = frappe.get_doc({"doctype": "Bot Skill", "skill_key": new_key(config["subject"], existing),
                              "action_type": "level_quiz", "missing_policy": "ask", "creates_lead": 1,
                              "sort_order": 160 + frappe.db.count("Bot Skill", {"action_type": "level_quiz"}),
                              "jev_description": f"The customer wants to test or check their {config['subject']} level"})
    subject = config["subject"]
    doc.title = (title or "").strip() or f"test trình độ {subject}"
    doc.aliases = (aliases or "").strip() or f"test {fold(subject)}, kiem tra {fold(subject)}"
    doc.active = 1 if str(active) in ("1", "true", "True") else 0
    doc.action_config = json.dumps(config, ensure_ascii=False, indent=1)
    rows = {t.variant_key: t for t in doc.templates}
    for key, text in templates.items():
        if key in rows:
            rows[key].template, rows[key].when = text, WHEN[key]
        else:
            doc.append("templates", {"variant_key": key, "when": WHEN[key], "template": text})
    if doc.is_new():
        doc.insert()
    else:
        doc.save()
    return _quiz_row(doc)


@whitelist()
def quiz_funnel(days=30):
    _require_access()
    days = int(days) if str(days).isdigit() and int(days) in PERIODS else 30
    since = frappe.utils.add_days(frappe.utils.today(), -days + 1)
    rows = [dict(r) for r in frappe.get_all(
        "Quiz Attempt", filters={"is_sandbox": 0, "creation": [">=", f"{since} 00:00:00"]}, limit_page_length=0,
        fields=["quiz", "lead", "status", "offered_at", "started_at", "phone_after", "reminded_at"])]
    leads = sorted({r["lead"] for r in rows if r.get("lead")})
    converted = set(frappe.get_all("CRM Lead", filters={"name": ["in", leads], "converted": 1}, pluck="name")) if leads else set()
    titles = dict(frappe.get_all("Bot Skill", filters={"action_type": "level_quiz"}, fields=["name", "title"], as_list=True))
    counts = funnel(rows, converted)
    return {"days": days, "since": since,
            "quizzes": [{"key": key, "title": titles.get(key, key), "counts": c,
                         "stages": [{"stage": label, "count": c[k]} for k, label in STAGES]}
                        for key, c in sorted(counts.items(), key=lambda kv: -kv[1]["offered"] - kv[1]["started"])]}
