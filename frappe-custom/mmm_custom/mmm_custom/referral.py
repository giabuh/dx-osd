"""Referral codes (D-103): every CRM Lead gets a short code (SV + 5 characters) that a student can pass
to friends. A new customer who writes the code in chat is recognised by the bot (slot type
`referral_code`); the Lead stores the code in `referred_by_code`, and on save the code is resolved to
`referred_by` and the Lead's source becomes "Giới thiệu", the one exception to first-touch sources
(D-100): a referral is what brought the customer, whichever channel they wrote from."""

import hashlib
import re

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

PREFIX = "SV"
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O or 1/I: codes are read aloud and retyped
CODE_RE = re.compile(rf"\b{PREFIX}[{ALPHABET}]{{5}}\b", re.IGNORECASE)
REFERRAL_SOURCE = "Giới thiệu"


def code_for(name, salt=0):
    """Deterministic code for a Lead name; `salt` picks another on the rare collision."""
    digest = hashlib.sha1(f"{name}:{salt}".encode()).digest()
    return PREFIX + "".join(ALPHABET[b % len(ALPHABET)] for b in digest[:5])


def find_code(text):
    """The first referral code written in a message, normalised to upper case ("" when none)."""
    m = CODE_RE.search(text or "")
    return m.group(0).upper() if m else ""


def _free_code(name):
    for salt in range(20):
        code = code_for(name, salt)
        if not frappe.db.exists("CRM Lead", {"referral_code": code}):
            return code
    frappe.throw("Không tạo được mã giới thiệu")


def set_code(doc, method=None):
    """CRM Lead before_insert."""
    if doc.meta.has_field("referral_code") and not doc.get("referral_code"):
        doc.referral_code = _free_code(doc.name or frappe.generate_hash(length=10))


def resolve_referrer(doc, method=None):
    """CRM Lead validate: a newly given code links the referrer and marks the source."""
    if not doc.meta.has_field("referred_by_code") or not doc.get("referred_by_code"):
        return
    code = find_code(doc.referred_by_code)
    if not code or (doc.get("referred_by") and not doc.has_value_changed("referred_by_code")):
        return
    referrer = frappe.db.get_value("CRM Lead", {"referral_code": code}, "name")
    if referrer and referrer != doc.name:
        doc.referred_by = referrer
        if frappe.db.exists("CRM Lead Source", REFERRAL_SOURCE):
            doc.source = REFERRAL_SOURCE


def backfill(limit=5000):
    """after_migrate: codes for Leads created before this feature."""
    for name in frappe.get_all("CRM Lead", filters={"referral_code": ["is", "not set"]}, pluck="name",
                               limit_page_length=limit):
        frappe.db.set_value("CRM Lead", name, "referral_code", _free_code(name), update_modified=False)
    frappe.db.commit()
