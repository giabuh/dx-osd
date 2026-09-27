"""Decide whether a turn may spend a Jev call; rejected calls use keyword understanding."""

HOUR = 3600


def recent_calls(calls, now):
    return [t for t in calls if now - t < HOUR]


def keywords_resolved(u, state):
    """Skip when all content is explained and any pending question is answered."""
    pending = state.pending.get("slot") or ""
    return not u.unmatched and (not pending or pending in u.fills or pending in u.parents)


def allow_jev(u, state, catalog, now, tokens_today=0, budget=0):
    settings = catalog.settings
    if u.tapped:
        return False, "button"
    if keywords_resolved(u, state):
        return False, "keywords_resolved"
    if len(recent_calls(state.jev_calls, now)) >= int(settings["jev_calls_per_hour"]):
        return False, "hourly_cap"
    if budget and tokens_today >= budget:
        return False, "daily_budget"
    return True, ""
