"""Level quiz (D-104): a few multiple-choice questions over Messenger buttons that place the customer
at a level and recommend a course — a free "test your Excel" hook that brings in Leads with a known
level. The quiz is data in its Bot Skill's `action_config`:

    {"slot": "quiz_progress", "subject": "Excel",
     "questions": [{"q": "...", "options": ["...", "..."], "answer": 0}, ...],
     "bands": [{"max": 2, "level": "beginner", "course": "VP-EXCEL"}, ...]}

No state is kept: each answer button carries every answer so far ("excel_quiz:0,1,2") in the
on-demand slot `quiz_progress`, so the next question and the score follow from the tap alone."""


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


def score(config, answers):
    questions = config.get("questions") or []
    return sum(1 for q, a in zip(questions, answers) if a == q.get("answer"))


def band(config, points):
    """The first band whose `max` covers the score (bands sorted by max), else the last."""
    bands = sorted(config.get("bands") or [], key=lambda b: b.get("max", 0))
    return next((b for b in bands if points <= b.get("max", 0)), bands[-1] if bands else {})


def result(config, answers):
    """None while unanswered questions remain, else {score, total, level, course}."""
    total = len(config.get("questions") or [])
    if not total or len(answers) < total:
        return None
    points = score(config, answers)
    b = band(config, points)
    return {"score": points, "total": total, "level": b.get("level", ""), "course": b.get("course", "")}


def summary(config, res, level_label=""):
    """One line for the Lead, e.g. "Excel: 4/5 · Biết cơ bản"."""
    text = f"{config.get('subject') or 'Test'}: {res['score']}/{res['total']}"
    return f"{text} · {level_label}" if level_label else text
