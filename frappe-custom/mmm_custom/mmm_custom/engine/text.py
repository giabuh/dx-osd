"""Text helpers for the keyword tier (D-028): Vietnamese diacritic folding, whole-word phrase search,
Vietnamese phone numbers."""

import re
import unicodedata

WORD_RE = re.compile(r"[a-z0-9]+")
PHONE_RE = re.compile(r"(?:\+?84|0)(?:[\s.\-]?\d){8,10}")
# Folded filler words ignored when collecting unmatched terms for learning signals (D-057).
STOPWORDS = frozenset(
    "cho toi minh em anh chi hoc khoa muon can hoi co khong the nao duoc voi nha nhe vay sao thi nhu bao "
    "nhieu lam roi dang biet giup xin chao cam on oke ok uhm uh".split())


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


def slug(text):
    return fold(text).replace(" ", "-")
