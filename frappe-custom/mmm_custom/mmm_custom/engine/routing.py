"""Consultant pick, rule D (D-006, D-087) — pure: branch + course-group specialty + hotness."""

CENTRAL_TEAM = "Tổng đài"
B2B_TEAM = "Doanh nghiệp (B2B)"
TEAM_LEAD = "Team Lead"


def pick_consultant(branch, consultants, load, owner="", group="", hot=False, b2b=False, online=None):
    """Returning customer → the Lead owner. Otherwise a company customer goes to the B2B consultants
    (D-099), anyone else to the branch's consultants (else the central team); a hot customer narrows it to team leads, a known course group to its specialists,
    each step only when someone qualifies; the least-loaded person of what is left gets the customer.
    Only consultants linked to a Chatwoot agent can be assigned. `online` (D-113): Chatwoot agent ids on duty now;
    when given, an offline owner is skipped and the people on duty are preferred at every step."""
    active = [c for c in consultants if c.get("active", 1) and c.get("chatwoot_agent_id")]

    def on_duty(c):
        return online is None or str(c.get("chatwoot_agent_id")) in online

    if owner:
        for c in active:
            if c["name"] == owner and on_duty(c):
                return c, "Khách quay lại · người phụ trách Lead"
    pool, why = ([c for c in active if c.get("handles_b2b")], [B2B_TEAM]) if b2b else ([], [])
    if not pool:
        pool, why = [c for c in active if branch and c.get("branch") == branch], [branch]
    if not pool:
        pool, why = [c for c in active if not c.get("branch") and not c.get("handles_b2b")], [CENTRAL_TEAM]
    if not pool:
        return None, "Chưa có tư vấn viên phù hợp"
    duty = [c for c in pool if on_duty(c)]
    if online is not None and duty:
        pool = duty
        why.append("đang trực")
    leads = [c for c in pool if c.get("level") == TEAM_LEAD]
    if hot and leads:
        pool = leads
        why.append("khách hot → trưởng nhóm")
    specialists = [c for c in pool if group and group in (c.get("specialties") or ())]
    if specialists:
        pool = specialists
        why.append(f"chuyên {group}")
    why.append("ít khách nhất")
    return min(pool, key=lambda c: (load.get(c["name"], 0), c["name"])), " · ".join(why)


def is_b2b(skills, catalog):
    """A company customer: one of the conversation's skills routes to B2B (`action_config.route`, D-099)."""
    return any(catalog.skills[k].config.get("route") == "b2b" for k in skills if k in catalog.skills)
