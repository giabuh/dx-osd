"""The one call to a generative model (Gemini), for text only staff read first (D-115). Customers never get
generated text: the bot's replies stay templates chosen by Jev (D-002, D-003), except
Facebook comment replies, which Gemini writes and comment_funnel.acceptable checks (D-129). Same configuration as the
Facebook post writer: `gemini_api_key` (site config) or GEMINI_API_KEY, model `gemini_model` or GEMINI_MODEL."""

import os

try:
    import requests
except ImportError:  # offline tests
    requests = None

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_MODEL = "gemini-3.8-flash"


def _conf():
    return (getattr(frappe, "conf", None) or {}) if frappe else {}


def api_key():
    return os.getenv("GEMINI_API_KEY") or _conf().get("gemini_api_key") or ""


def generate(prompt, system="", timeout=20, temperature=0.3, post=None):
    """The model's text for `prompt`, or None when no key is configured or the call fails."""
    key = api_key()
    if not key:
        return None
    model = _conf().get("gemini_model") or os.getenv("GEMINI_MODEL") or DEFAULT_MODEL
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": temperature}}
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    try:
        resp = (post or requests.post)(GEMINI_URL.format(model=model), params={"key": key}, json=body, timeout=timeout)
        resp.raise_for_status()
        return resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip() or None
    except Exception:
        if frappe and hasattr(frappe, "log_error"):
            frappe.log_error(title="Gemini draft failed")
        return None
