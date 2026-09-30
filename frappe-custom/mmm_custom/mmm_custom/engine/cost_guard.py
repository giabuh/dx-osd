"""Decide whether a turn may spend a Jev call; rejected calls use keyword understanding."""

HOUR = 3600


def recent_calls(calls, now):
    return [t for t in calls if now - t < HOUR]


def keywords_resolved(u, state):
    """Skip when all content is explained and any pending question is answered."""
    pending = state.pending.get("slot") or ""
    return not u.unmatched and (not pending or pending in u.fills or pending in u.parents)


def library_has(u, state, catalog, text):
    """Staff once answered something like this (D-114): worth asking Jev even when keywords explain it all."""
    from mmm_custom.engine import staff_replies
    from mmm_custom.engine.jev_questions import known_course

    return bool(text) and bool(staff_replies.candidates(catalog, text, known_course(state, u, catalog), "",
                                                        state.drafting, limit=1))


def allow_jev(u, state, catalog, now, tokens_today=0, budget=0, text=""):
    settings = catalog.settings
    if state.status == "closed" or state.consultant_replied:
        return False, "bot_silent"  # decide() stays silent: a Jev call would be spent for nothing
    if u.tapped:
        return False, "button"
    if u.greeting:
        return False, "greeting"  # nothing to understand, and a greeting must never read as a button (D-109)
    if keywords_resolved(u, state) and not library_has(u, state, catalog, text):
        return False, "keywords_resolved"
    if len(recent_calls(state.jev_calls, now)) >= int(settings["jev_calls_per_hour"]):
        return False, "hourly_cap"
    if budget and tokens_today >= budget:
        return False, "daily_budget"
    return True, ""
