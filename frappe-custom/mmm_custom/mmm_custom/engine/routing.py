"""Consultant pick, rule D (D-006, D-087) — pure: branch + course-group specialty + hotness."""

CENTRAL_TEAM = "Tổng đài"
B2B_TEAM = "Doanh nghiệp (B2B)"
TEAM_LEAD = "Team Lead"


def pick_consultant(branch, consultants, load, owner="", group="", hot=False):
    """Returning customer → the Lead owner. Otherwise the pool is the branch's consultants (else the
    central team); a hot customer narrows it to team leads, a known course group to its specialists,
    each step only when someone qualifies; the least-loaded person of what is left gets the customer.
    Only consultants linked to a Chatwoot agent can be assigned."""
    active = [c for c in consultants if c.get("active", 1) and c.get("chatwoot_agent_id")]
    if owner:
        for c in active:
            if c["name"] == owner:
                return c, "Khách quay lại · người phụ trách Lead"
    pool, why = [c for c in active if branch and c.get("branch") == branch], [branch]
    if not pool:
        pool, why = [c for c in active if not c.get("branch") and not c.get("handles_b2b")], [CENTRAL_TEAM]
    if not pool:
        return None, "Chưa có tư vấn viên phù hợp"
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
