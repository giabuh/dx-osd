"""Level-test reward (D-106): once a customer who took the level test leaves a phone number, the bot sends
the recommended course's syllabus and, when a promotion applies to that course, a personal voucher code.
Pure, no I/O: the code is derived from the conversation, so a replayed turn gives the same code."""

import hashlib

from mmm_custom.engine.text import fold

ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"  # no 0/O, 1/I: read out over the phone
SUBJECT_LEN = 8


def code(prefix, subject, seed):
    """e.g. "SV-EXCEL-7K3Q": brand prefix, quiz subject, four characters from the conversation."""
    digest = hashlib.sha1(f"{seed}:{subject}".encode()).digest()
    tail = "".join(ALPHABET[b % len(ALPHABET)] for b in digest[:4])
    word = "".join(ch for ch in fold(subject).upper() if ch.isalnum())[:SUBJECT_LEN] or "TEST"
    return "-".join(x for x in (str(prefix or "").strip().upper(), word, tail) if x)


def best_promotion(promotions, course, branch, applicable, discount):
    """(promotion, amount off) of the promotion worth most for this course, or (None, 0)."""
    best, amount = None, 0
    for p in promotions:
        if applicable(p, course, branch):
            off = discount(p, course["fee"])
            if off > amount:
                best, amount = p, off
    return best, amount
