"""Text helpers for the keyword tier (D-028): Vietnamese diacritic folding, whole-word phrase search,
Vietnamese phone numbers."""

import html
import re
import unicodedata

WORD_RE = re.compile(r"[a-z0-9]+")
TAG_RE = re.compile(r"<[^>]+>")
PHONE_RE = re.compile(r"(?:\+?84|0)(?:[\s.\-]?\d){8,10}")
# Folded filler words ignored when collecting unmatched terms for learning signals (D-057).
STOPWORDS = frozenset(
    "cho toi minh em anh chi hoc khoa muon can hoi co khong the nao duoc voi nha nhe vay sao thi nhu bao "
    "nhieu lam roi dang biet giup xin chao cam on oke ok uhm uh".split())


# A message made only of these (folded) words, with at least one greeting or laugh, is small talk (D-109):
# "hihi", "chào em", "alo ad ơi", "hello shop ạ", "chào buổi sáng".
GREETING_RE = re.compile(r"(?:chao+|hi+|hello+|hel+o+|a+lo+|hey+|(?:h[aeiu]+){2,}|(?:k[ae]+){2,}|(?:hj+)+)")
SMALLTALK_WORDS = frozenset(
    "xin a ad admin shop page trung tam em anh chi ban moi nguoi ca nha oi nhe nha ne da vang buoi sang trua chieu "
    "toi".split())
MAX_SMALLTALK_WORDS = 6


def fold(text):
    """Lowercase, drop Vietnamese diacritics (đ → d) and punctuation: "Dĩ An, Q.7" → "di an q 7"."""
    text = (text or "").lower().replace("đ", "d")
    text = "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")
    return " ".join(WORD_RE.findall(text))


def find_phrases(folded_text, table, min_words=1):
    """Values whose phrases occur as whole words in `folded_text`, as {value: (start, end)}.

    A hit lying inside a longer hit of another value is dropped, so "excel nang cao" beats "excel".
    Positions index into `folded_text`.
    """
    padded = f" {folded_text} "
    hits = []
    for value, phrases in table.items():
        for phrase in phrases:
            p = fold(phrase)
            if not p or len(p.split()) < min_words:
                continue
            at = padded.find(f" {p} ")
            if at >= 0:
                hits.append((at, at + len(p), value))
    best = {}
    for s, e, v in hits:
        if any(s2 <= s and e <= e2 and e2 - s2 > e - s and v2 != v for s2, e2, v2 in hits):
            continue
        if v not in best or e - s > best[v][1] - best[v][0]:
            best[v] = (s, e)
    return best


def content_words(folded_text, spans):
    """Words of 3+ letters that no matched phrase covers and that are not filler."""
    out = []
    for m in WORD_RE.finditer(folded_text):
        word = m.group()
        if len(word) < 3 or word.isdigit() or word in STOPWORDS:
            continue
        if any(s <= m.start() and m.end() <= e for s, e in spans):
            continue
        out.append(word)
    return list(dict.fromkeys(out))


def is_smalltalk(folded_text):
    """True for a greeting or a laugh with nothing else in it: "hihi", "chao em", "alo ad oi"."""
    words = (folded_text or "").split()
    if not words or len(words) > MAX_SMALLTALK_WORDS:
        return False
    greetings = [w for w in words if GREETING_RE.fullmatch(w)]
    return bool(greetings) and all(w in SMALLTALK_WORDS or GREETING_RE.fullmatch(w) for w in words)


def normalize_vn_phone(raw):
    """0901234567 / +84 901 234 567 / 84901234567 → +84901234567; anything else → None."""
    digits = re.sub(r"[\s.\-()]+", "", (raw or "").strip())
    if digits.startswith("+84"):
        digits = "0" + digits[3:]
    elif digits.startswith("84") and len(digits) == 11:
        digits = "0" + digits[2:]
    return "+84" + digits[1:] if re.fullmatch(r"0\d{9}", digits) else None


def find_phone(text):
    for m in PHONE_RE.finditer(text or ""):
        phone = normalize_vn_phone(m.group(0))
        if phone:
            return phone
    return None


PHONE_LIKE_RE = re.compile(r"(?<![\d.,])(?:\+?84|0)(?:[\s.\-]?\d){7,11}(?![\d.,]*\d)")


def find_phone_candidate(text):
    """Digits that look like a Vietnamese phone number but are not one (a digit missing or extra), as the
    customer wrote them without separators; None when there is a valid number or nothing phone-like."""
    if find_phone(text):
        return None
    for m in PHONE_LIKE_RE.finditer(text or ""):
        digits = re.sub(r"[\s.\-]", "", m.group(0))
        if 9 <= len(digits.lstrip("+")) <= 12:
            return digits
    return None


NAME_AFTER_TEN_RE = re.compile(r"(?:^|\s)t[eê]n\s+(?:(?:c[uủ]a\s+)?(?:em|m[iì]nh|t[oô]i|anh|ch[iị]|con|ch[aá]u)\s+)?"
                               r"(?:l[aà]\s+)?(.+)", re.IGNORECASE)
NAME_LEAD_RE = re.compile(r"^(?:d[aạ]\s+|v[aâ]ng\s+)?(?:(?:em|m[iì]nh|t[oô]i|anh|ch[iị])\s+)?(?:l[aà]\s+|t[eê]n\s+)?"
                          r"(?:(?:anh|ch[iị]|c[oô]|ch[uú])\s+)?", re.IGNORECASE)
NAME_STOP_RE = re.compile(r"[,.;:!?\n]|\s(?:s[dđ]t|s[oố]\b|đi[eệ]n tho[aạ]i|h[oọ]c\b|mu[oố]n\b|nh[eé]\b|nha\b|"
                          r"[aạ]\b|nh[aá]\b|ơi\b)", re.IGNORECASE)
MAX_NAME_WORDS = 4
NOT_NAMES = frozenset("ok oke okie okay vang da dung khong ko co roi duoc chua uh um a nhe nha em anh chi minh toi "
                      "ban thoi hi hello alo chao xin cam on hoc lop khoa gi nao sao the".split())
CHILD_NAME_RE = re.compile(r"\b(?:con|chau|be)\s+(?:(?:em|minh|toi|nha em)\s+)?ten\b|\bten\s+(?:cua\s+)?(?:con|chau|be)\b")


def clean_name(raw):
    """"hùng ạ" → "Hùng"; None when it does not look like a person's name."""
    text = NAME_STOP_RE.split(" " + (raw or "").strip(), maxsplit=1)[0].strip()
    words = text.split()
    if not words or len(words) > MAX_NAME_WORDS or not all(w.isalpha() for w in words):
        return None
    if any(fold(w) in NOT_NAMES for w in words):
        return None
    return " ".join(w[:1].upper() + w[1:].lower() for w in words)


def extract_name(text, asked=False):
    """The customer's name from "mình tên Hùng", "tên em là nguyễn văn an ạ", or, when the bot has just
    asked for it, a bare answer such as "Hùng" / "em là Lan". None otherwise."""
    if CHILD_NAME_RE.search(fold(text)):
        return None  # "con tên là Bin": the child's name, not the customer's
    m = NAME_AFTER_TEN_RE.search(text or "")
    if m:
        return clean_name(m.group(1))
    if asked:
        return clean_name(NAME_LEAD_RE.sub("", (text or "").strip(), count=1))
    return None


def slug(text):
    return fold(text).replace(" ", "-")


def plain_text(markup):
    """Text Editor HTML as one line of plain text for templates: "<p>A&amp;B</p>" → "A&B"."""
    return " ".join(html.unescape(TAG_RE.sub(" ", markup or "")).split())
