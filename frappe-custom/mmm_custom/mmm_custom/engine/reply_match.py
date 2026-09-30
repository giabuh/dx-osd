"""What a typed message answers among the buttons the bot just offered (D-107). Pure, no I/O.

Customers rarely tap: they type "sumif", "câu b", "ok", "thôi để sau", "học thử thứ 7 ngày 3/10". Every
turn with buttons stores them in `state.pending["options"]` (title → action); `match_pending` maps such a
message to one of those actions, or returns None and lets the rest of the keyword tier (and Jev's
`reply_to_bot` question) read it."""

import re

from mmm_custom.engine.text import fold

YES = frozenset({"ok", "oke", "okie", "okay", "ok em", "oke em", "ok a", "duoc", "duoc a", "duoc em", "dong y", "co",
                 "co a", "co em", "vang", "da", "da vang", "da duoc", "u", "uh", "um", "lam", "lam thu", "lam luon",
                 "lam di", "thu", "thu xem", "ok lam", "ok lam thu", "ok luon", "chac chan roi", "nhat tri"})
NO = frozenset({"khong", "ko", "k", "khong a", "khong em", "thoi", "thoi a", "thoi em", "de sau", "de sau nhe",
                "de khi khac", "luc khac", "khi khac", "khong lam", "khong can", "chua", "chua can", "ban", "dang ban",
                "thoi khong lam", "khong lam dau", "de sau a"})
REFUSALS = ("khong can", "khong muon", "khong thich", "khong co nhu cau", "chua muon", "khoi")
REFUSAL_WORDS = 8
LETTERS = "abcdefgh"
INDEX_RE = re.compile(r"^(?:cau|dap an|chon|phuong an|dap an la|chon cau|toi chon|em chon|minh chon)?\s*([a-h]|[1-8])$")
DATE_RE = re.compile(r"(\d{1,2})\s*[/\-.]\s*(\d{1,2})")
DAY_RE = re.compile(r"\bngay\s+(\d{1,2})\b")
MONTH_RE = re.compile(r"\bthang\s+(\d{1,2})\b")
CLASS_TITLE_RE = re.compile(r"(\d{2})/(\d{2})\s+(\S+)\s*(.*)")
WEEKDAY_RE = re.compile(r"\b(?:thu\s*|t)([2-7])\b|\b(chu nhat|cn)\b")
SHIFTS = ("sang", "chieu", "toi")
WEEKDAY_WORDS = {"thu hai": "2", "thu ba": "3", "thu tu": "4", "thu nam": "5", "thu sau": "6", "thu bay": "7"}


def _kinds(options):
    return {a.get("type") for a in options.values()}


def is_quiz(options):
    return bool(options) and all(a.get("type") == "slot" and a.get("slot") == "quiz_progress" for a in options.values())


def is_offer(options):
    return {"skill", "offer_decline"} <= _kinds(options)


def is_trial(options):
    return bool(options) and all(a.get("type") == "slot" and a.get("slot") == "trial_class" for a in options.values())


def yes_no(folded):
    """True / False / None for a short agreeing or refusing message."""
    text = re.sub(r"\b(a|nhe|nha|nhe em|ha|luon a)$", "", folded).strip() or folded
    if folded in YES or text in YES:
        return True
    if folded in NO or text in NO or text.startswith(("thoi ", "de sau", "khong lam")) or _refuses(text):
        return False
    return None


def _refuses(text):
    """"không cần đâu", "mình không muốn làm test", "khỏi test nha": a short refusal. A long message is left
    alone, it usually carries a question of its own ("không cần test, cho mình hỏi học phí…")."""
    text = re.sub(r"^(minh|em|toi|anh|chi)\s+", "", text)
    return len(text.split()) <= REFUSAL_WORDS and text.startswith(REFUSALS)


def _by_title(folded, options):
    exact = [a for t, a in options.items() if fold(t) == folded]
    if exact:
        return exact[0]
    inside = [a for t, a in options.items() if len(fold(t)) >= 4 and f" {fold(t)} " in f" {folded} "]
    return inside[0] if len(inside) == 1 else None


def _by_index(folded, options):
    m = INDEX_RE.match(folded)
    if not m:
        return None
    key = m.group(1)
    index = LETTERS.index(key) if key in LETTERS else int(key) - 1
    actions = list(options.values())
    return actions[index] if 0 <= index < len(actions) else None


def _trial_parts(text):
    """(day, month, weekday, shift) the customer wrote; each may be None."""
    folded = fold(text)
    for words, digit in WEEKDAY_WORDS.items():
        folded = re.sub(rf"\b{words}\b", f"thu {digit}", folded)
    day = month = weekday = shift = None
    m = DATE_RE.search(text or "")
    if m:
        day, month = int(m.group(1)), int(m.group(2))
    else:
        d = DAY_RE.search(folded)
        day = int(d.group(1)) if d else None
    w = WEEKDAY_RE.search(folded)
    if w:
        weekday = "CN" if w.group(2) else f"T{w.group(1)}"
    shift = next((s for s in SHIFTS if re.search(rf"\b{s}\b", folded)), None)
    return day, month, weekday, shift


def _by_date(text, options):
    """Trial buttons are titled like "T7 03/10 Tối"; pick the only one matching what was written."""
    day, month, weekday, shift = _trial_parts(text)
    if not (day or weekday):
        return None
    hits = []
    for title, action in options.items():
        m = re.match(r"(T[2-7]|CN)\s+(\d{2})/(\d{2})\s*(.*)", title)
        if not m:
            continue
        tw, td, tm, ts = m.group(1), int(m.group(2)), int(m.group(3)), fold(m.group(4))
        if (day and day != td) or (month and month != tm) or (weekday and weekday != tw) or (shift and shift not in ts):
            continue
        hits.append(action)
    return hits[0] if len(hits) == 1 else None


def match_class(text, pending, slot):
    """The registration class button (titled "05/10 Sáng Quận 6", D-121) a typed message picks, even inside a longer
    message that also asks something ("sáng quận 6 ngày 5 tháng 10, học phí sao"): the only button that fits the day,
    month, shift and branch written. Needs a day, or a branch with a shift: "quận 6 nằm đâu" only names a branch."""
    options = {t: a for t, a in ((pending or {}).get("options") or {}).items()
               if a.get("type") == "slot" and a.get("slot") == slot}
    if not options:
        return None
    folded = fold(text)
    day, month, _, shift = _trial_parts(text)
    m = MONTH_RE.search(folded)
    month = month or (int(m.group(1)) if m else None)
    parsed = {t: CLASS_TITLE_RE.match(t) for t in options}
    branches = {t: fold(p.group(4)) for t, p in parsed.items() if p and p.group(4)}
    named = any(b and b in folded for b in branches.values())
    if not (day or (named and shift)):
        return None
    hits = []
    for title, p in parsed.items():
        if not p:
            continue
        if (day and day != int(p.group(1))) or (month and month != int(p.group(2))) or \
                (shift and shift != fold(p.group(3))) or (named and branches.get(title, "") not in folded):
            continue
        hits.append(options[title])
    return hits[0] if len(hits) == 1 else None


def match_pending(text, pending):
    """The action of the offered button this message means, or None."""
    options = (pending or {}).get("options") or {}
    if not options:
        return None
    folded = fold(text)
    if not folded:
        return None
    if is_offer(options) and yes_no(folded) is False:  # "không thích làm bài test" names the start button
        return next(a for a in options.values() if a.get("type") == "offer_decline")
    action = _by_title(folded, options)
    if action:
        return action
    if is_quiz(options):
        if yes_no(folded) is False or folded.startswith(("khong lam nua", "thoi khong lam", "dung lai", "ngung")):
            return {"type": "offer_decline", "skill": next(iter(options.values())).get("skill", "")}
        return _by_index(folded, options)
    if is_trial(options):
        return _by_date(text, options)
    if is_offer(options):
        answer = yes_no(folded)
        if answer is not None:
            wanted = "skill" if answer else "offer_decline"
            return next(a for a in options.values() if a.get("type") == wanted)
    return None
