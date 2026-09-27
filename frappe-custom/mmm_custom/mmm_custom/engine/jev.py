"""TypeSafe Jev in the bot path (D-028, D-031, D-076): one System One call with parallel typed
questions and an 8 s budget. Any failure returns status "unavailable" and the turn continues on
the keyword tier; Jev never writes text (D-003)."""

import time
from dataclasses import dataclass, field

try:
    import requests
except ImportError:  # offline tests
    requests = None

JEV_URL = "https://api.typesafe.ai/v1/systemone"
RETRYABLE = ("ConnectionError", "RemoteDisconnected", "ChunkedEncodingError")


@dataclass
class JevResult:
    status: str  # ok | unavailable | disabled | skipped_cost_guard (D-056)
    answers: dict = field(default_factory=dict)
    questions: dict = field(default_factory=dict)
    model: str = ""
    input_tokens: int = 0
    latency_ms: int = 0
    error: str = ""

    def log(self):
        return {"status": self.status, "questions": self.questions, "answers": self.answers, "model": self.model,
                "latency_ms": self.latency_ms, "input_tokens": self.input_tokens, "error": self.error}


class JevClient:
    def __init__(self, api_key, model="jev-latest", url=JEV_URL, timeout=8.0, post=None, clock=time.monotonic):
        self.api_key, self.model, self.url, self.timeout = api_key, model, url, float(timeout)
        self.post = post or (lambda *args, **kwargs: requests.post(*args, **kwargs))
        self.clock = clock

    def _ms(self, start):
        return int((self.clock() - start) * 1000)

    def ask(self, state, questions):
        if not questions:
            return JevResult("ok")
        start, error = self.clock(), ""
        body = {"model": self.model, "state": state, "questions": questions}
        for attempt in range(2):
            try:
                resp = self.post(self.url, headers={"Authorization": f"Bearer {self.api_key}"}, json=body,
                                 timeout=max(self.timeout - (self.clock() - start), 1.0))
                resp.raise_for_status()
                data = resp.json()
                return JevResult("ok", dict(data.get("answers") or {}), questions, data.get("model") or "",
                                 int((data.get("usage") or {}).get("input_tokens") or 0), self._ms(start))
            except Exception as e:
                error = f"{type(e).__name__}: {e}"[:300]
                if attempt or type(e).__name__ not in RETRYABLE or self.clock() - start > self.timeout / 2:
                    break
        return JevResult("unavailable", questions=questions, latency_ms=self._ms(start), error=error)


def jev_client(conf, settings, force=None):
    """The client for this turn, or None: no key, forced off, or not live yet (D-073)."""
    key = conf.get("typesafe_api_key")
    if not key or force is False or not (force or settings.get("jev_live")):
        return None
    return JevClient(key, conf.get("typesafe_model") or "jev-latest", conf.get("typesafe_api_url") or JEV_URL,
                     timeout=float(settings.get("jev_timeout") or 8))
