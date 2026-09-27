"""Level quiz (D-104, adaptive since D-106): a few multiple-choice questions over Messenger buttons that
place the customer at a level and recommend a course — a free "test your level" hook that brings in Leads
with a known level. The quiz is data in its Bot Skill's `action_config`:

    {"slot": "quiz_progress", "subject": "Excel",
     "courses": ["VP-EXCEL", ...], "groups": ["Tin học văn phòng"],   # when the bot offers it (engine/offers.py)
     "mode": "test",                     # test: one right answer · survey: points per option (asking a parent)
     "max_questions": 5, "stop_after_wrong": 2,
     "questions": [{"q": "...", "options": ["...", "..."], "answer": 0, "points": [2, 1, 0],
                    "level": "basic|intermediate|advanced", "topic": "VLOOKUP", "goals": ["office"]}, ...],
     "bands": [{"max": 2, "level": "beginner", "course": "VP-EXCEL"}, ...]}

Adaptive without state: the questions are asked easy → hard (filtered by the customer's `goal`), so the
answers so far ("excel_quiz:0,1,2" in the on-demand slot `quiz_progress`) are enough to know which
question comes next, whether the quiz stops early (two basic questions wrong → no point going harder),
and the score. A configuration without levels keeps its original order (D-104)."""

LEVEL_ORDER = {"basic": 0, "intermediate": 1, "advanced": 2}
MODES = ("test", "survey")
MAX_BUTTON = 20  # Messenger quick reply title limit


def progress(raw, skill_key):
    """Answers so far for this quiz from the slot value, or [] (another quiz's progress counts as none)."""
    prefix, _, rest = str(raw or "").partition(":")
    if prefix != skill_key:
        return []
    try:
        return [int(x) for x in rest.split(",") if x != ""]
    except ValueError:
        return []


def encode(skill_key, answers):
    return f"{skill_key}:{','.join(str(a) for a in answers)}"


def order(config, goal=""):
    """Indexes of the questions this customer gets, easy → hard. Questions tagged with other goals are
    left out unless that leaves too few to fill the quiz."""
    questions = config.get("questions") or []
    fits = [i for i, q in enumerate(questions) if not goal or not q.get("goals") or goal in q["goals"]]
    wanted = min(int(config.get("max_questions") or len(questions)), len(questions))
    pool = fits if len(fits) >= wanted else list(range(len(questions)))
    return sorted(pool, key=lambda i: (LEVEL_ORDER.get(questions[i].get("level"), 1), i))


def limit(config, goal=""):
    return min(int(config.get("max_questions") or len(config.get("questions") or [])), len(order(config, goal)))


def asked(config, answers, goal=""):
    """[(question index, answer)] for the answers so far."""
    return list(zip(order(config, goal), answers))


def is_right(question, answer):
    return answer == question.get("answer")


def _points(question, answer):
    points = question.get("points") or []
    return points[answer] if 0 <= answer < len(points) else 0


def wrong_basics(config, answers, goal=""):
    questions = config.get("questions") or []
    return sum(1 for i, a in asked(config, answers, goal)
               if questions[i].get("level") == "basic" and not is_right(questions[i], a))


def finished(config, answers, goal=""):
    if not config.get("questions"):
        return True
    if len(answers) >= limit(config, goal):
        return True
    stop = int(config.get("stop_after_wrong") or 0)
    return config.get("mode", "test") == "test" and bool(stop) and wrong_basics(config, answers, goal) >= stop


def next_question(config, answers, goal=""):
    """(index, question) to ask now, or None when the quiz is over."""
    if finished(config, answers, goal):
        return None
    i = order(config, goal)[len(answers)]
    return i, config["questions"][i]


def last_correct(config, answers, goal=""):
    """Whether the latest answer was right (None in a survey or before the first answer): the next
    question opens with a word of praise or encouragement."""
    if not answers or config.get("mode", "test") != "test":
        return None
    i, a = asked(config, answers, goal)[-1]
    return is_right(config["questions"][i], a)


def score(config, answers, goal=""):
    questions = config.get("questions") or []
    pairs = asked(config, answers, goal)
    if config.get("mode", "test") == "survey":
        return sum(_points(questions[i], a) for i, a in pairs)
    return sum(1 for i, a in pairs if is_right(questions[i], a))


def total(config, answers, goal=""):
    questions = config.get("questions") or []
    pairs = asked(config, answers, goal)
    if config.get("mode", "test") == "survey":
        return sum(max(questions[i].get("points") or [0]) for i, _ in pairs)
    return len(pairs)


def missed_topics(config, answers, goal=""):
    """Topics of the wrong answers, in order and without repeats (for the consultant)."""
    if config.get("mode", "test") != "test":
        return []
    questions, out = config.get("questions") or [], []
    for i, a in asked(config, answers, goal):
        topic = questions[i].get("topic") or questions[i].get("q", "")
        if not is_right(questions[i], a) and topic not in out:
            out.append(topic)
    return out


def band(config, points):
    """The first band whose `max` covers the score (bands sorted by max), else the last."""
    bands = sorted(config.get("bands") or [], key=lambda b: b.get("max", 0))
    return next((b for b in bands if points <= b.get("max", 0)), bands[-1] if bands else {})


def result(config, answers, goal=""):
    """None while the quiz goes on, else {score, total, level, course, missed, stopped_early}."""
    if not config.get("questions") or not finished(config, answers, goal):
        return None
    points = score(config, answers, goal)
    b = band(config, points)
    return {"score": points, "total": total(config, answers, goal), "level": b.get("level", ""),
            "course": b.get("course", ""), "missed": missed_topics(config, answers, goal),
            "stopped_early": len(answers) < limit(config, goal)}


def summary(config, res, level_label=""):
    """One line for the Lead, e.g. "Excel: 4/5 · Biết cơ bản"."""
    text = f"{config.get('subject') or 'Test'}: {res['score']}/{res['total']}"
    return f"{text} · {level_label}" if level_label else text


def quiz_for(skills, course="", group=""):
    """The level quiz to offer for a course (its own quiz first, else one for its group), or ""."""
    quizzes = sorted((s for s in skills.values() if s.action == "level_quiz"), key=lambda s: s.order)
    for s in quizzes:
        if course and course in (s.config.get("courses") or []):
            return s.key
    for s in quizzes:
        if group and group in (s.config.get("groups") or []):
            return s.key
    return ""


def validate(config, course_codes=(), levels=()):
    """What is wrong with a quiz configuration a manager saves ([] when fine). Pure."""
    errors = []
    questions = config.get("questions") or []
    mode = config.get("mode", "test")
    if mode not in MODES:
        errors.append(f"Chế độ không hợp lệ: {mode}")
    if not questions:
        errors.append("Cần ít nhất một câu hỏi.")
    for n, q in enumerate(questions, 1):
        options = q.get("options") or []
        if not str(q.get("q") or "").strip():
            errors.append(f"Câu {n}: thiếu nội dung câu hỏi.")
        if len(options) < 2:
            errors.append(f"Câu {n}: cần ít nhất 2 lựa chọn.")
        long = [o for o in options if len(str(o)) > MAX_BUTTON]
        if long:
            errors.append(f"Câu {n}: lựa chọn dài quá {MAX_BUTTON} ký tự (nút Messenger): {long[0]}")
        if mode == "test" and not (isinstance(q.get("answer"), int) and 0 <= q["answer"] < len(options)):
            errors.append(f"Câu {n}: chọn đáp án đúng.")
        if mode == "survey" and len(q.get("points") or []) != len(options):
            errors.append(f"Câu {n}: cần điểm cho từng lựa chọn.")
        if q.get("level") and q["level"] not in LEVEL_ORDER:
            errors.append(f"Câu {n}: mức độ không hợp lệ ({q['level']}).")
    bands = config.get("bands") or []
    if not bands:
        errors.append("Cần ít nhất một ngưỡng điểm để xếp trình độ.")
    for b in bands:
        if course_codes and b.get("course") and b["course"] not in course_codes:
            errors.append(f"Ngưỡng ≤ {b.get('max')}: không có khóa {b['course']}.")
        if levels and b.get("level") not in levels:
            errors.append(f"Ngưỡng ≤ {b.get('max')}: trình độ không hợp lệ ({b.get('level')}).")
    return errors
