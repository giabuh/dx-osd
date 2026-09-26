"""C2.6 consultant pick (D-058) — pure. C4.1 replaces it with full rule D (branch + specialty + hotness)."""

CENTRAL_TEAM = "Tổng đài"
B2B_TEAM = "Doanh nghiệp (B2B)"


def pick_consultant(branch, consultants, load, owner=""):
    """Returning customer → the Lead owner; else the least-loaded consultant of the branch; else the
    least-loaded central consultant. Only consultants linked to a Chatwoot agent can be assigned."""
    active = [c for c in consultants if c.get("active", 1) and c.get("chatwoot_agent_id")]
    if owner:
        for c in active:
            if c["name"] == owner:
                return c, "Khách quay lại · người phụ trách Lead"
    pool, why = [c for c in active if branch and c.get("branch") == branch], f"{branch} · ít khách nhất"
    if not pool:
        pool = [c for c in active if not c.get("branch") and not c.get("handles_b2b")]
        why = f"{CENTRAL_TEAM} · ít khách nhất"
    if not pool:
        return None, "Chưa có tư vấn viên phù hợp"
    return min(pool, key=lambda c: (load.get(c["name"], 0), c["name"])), why
