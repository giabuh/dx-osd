"""Course advisor scoring (D-040, D-055, D-079): Jev scores how well each shortlisted course fits the
customer's goal and level (0–2) and whether anything rules it out; code computes the composite."""

GOAL_FIT = ["0: does not serve what the customer wants to achieve", "1: partly serves it",
            "2: clearly serves what the customer wants to achieve"]
LEVEL_FIT = ["0: wrong level for the customer (too hard or too basic)", "1: acceptable level",
             "2: exactly the customer's level"]
EXCLUDE_AT = 0.70


def _about(c):
    ages = f"; ages {c.min_age}–{c.max_age}" if c.min_age or c.max_age else ""
    return f"'{c.name}' (group: {c.group}; for: {c.audience}{ages})"


def advisor_questions(courses):
    q = {}
    for c in courses:
        about = _about(c)
        q[f"goal_fit:{c.code}"] = {"type": "score", "criteria": GOAL_FIT,
                                   "instructions": f"How well does the course {about} fit what the customer wants to achieve?"}
        q[f"level_fit:{c.code}"] = {"type": "score", "criteria": LEVEL_FIT,
                                    "instructions": f"How well does the course {about} match the customer's current level?"}
        q[f"exclude:{c.code}"] = {"type": "noul", "instructions":
                                  f"Does anything in the chat rule out the course {about} (wrong age, already taken, explicitly not wanted)?"}
    return q


def _num(answers, key, field):
    try:
        return float((answers.get(key) or {})[field])
    except (KeyError, TypeError, ValueError):
        return None


def score_courses(courses, answers, settings):
    gw, lw = float(settings["advisor_goal_weight"]), float(settings["advisor_level_weight"])
    ranked = []
    for c in courses:
        goal, level = _num(answers, f"goal_fit:{c.code}", "score"), _num(answers, f"level_fit:{c.code}", "score")
        if goal is None or level is None or (_num(answers, f"exclude:{c.code}", "noul") or 0) >= EXCLUDE_AT:
            continue
        ranked.append((c, round(gw * min(max(goal, 0), 2) / 2 + lw * min(max(level, 0), 2) / 2, 3)))
    return sorted(ranked, key=lambda pair: -pair[1])  # stable: ties keep the data order
