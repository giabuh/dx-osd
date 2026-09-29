"""CRM → Chatwoot staff sync: CRM is the only place where branches and consultants are managed.

Every consultant becomes a Chatwoot agent, each branch a Chatwoot team holding exactly its active
consultants (plus B2B and the central team), and every Facebook page inbox gets the lead-engine bot.
A page connected with a branch (Channel Connection.branch) gets that branch's consultants as inbox members;
on other pages inbox membership is granted at handoff (engine.effects), so nobody is added to all pages up front.
Membership is only ever added: a consultant handed a conversation from another branch keeps their access.
Runs on Consultant save and every 10 minutes (hooks.py); every step is idempotent.

Manual run: bench --site crm.localhost execute mmm_custom.staff_sync.sync_now
"""

import logging

try:
    import frappe
except ImportError:  # offline tests
    frappe = None

from mmm_custom.chatwoot_client import ChatwootClient
from mmm_custom.engine.routing import B2B_TEAM, CENTRAL_TEAM

logger = logging.getLogger(__name__)

BOT_CHANNELS = ("Channel::FacebookPage",)
BOT_WEBHOOK = "mmm_custom.bot_api"


def plan_teams(consultants):
    """Team name → emails of the active consultants who belong to it."""
    teams = {}
    for c in consultants:
        if not c.get("active", 1):
            continue
        team = c.get("branch") or (B2B_TEAM if c.get("handles_b2b") else CENTRAL_TEAM)
        teams.setdefault(team, []).append(c["email"])
    return teams


def ensure_agents(client, consultants):
    existing = {a["email"]: a["id"] for a in client.list_agents()}
    ids = {}
    for c in consultants:
        if not c.get("active", 1):
            continue
        if c["email"] not in existing:
            existing[c["email"]] = client.create_agent(c.get("full_name") or c["email"], c["email"])["id"]
        ids[c["email"]] = existing[c["email"]]
    return ids


def sync_teams(client, consultants, ids, branches):
    """Create missing teams and set each managed team's members; a team named after a branch that has
    no active consultant left is emptied. Chatwoot stores team names lowercased."""
    teams = {t["name"].lower(): t["id"] for t in client.list_teams()}
    wanted = {}
    for name, emails in plan_teams(consultants).items():
        if name.lower() not in teams:
            teams[name.lower()] = client.create_team(name)["id"]
        wanted[name.lower()] = sorted(ids[e] for e in emails)
    managed = set(wanted) | {n.lower() for n in (*branches, B2B_TEAM, CENTRAL_TEAM)}
    for key, team_id in teams.items():
        if key in managed:
            client.update_team_members(team_id, wanted.get(key, []))
    return len(wanted)


def sync_inboxes(client):
    """Attach the lead-engine bot to every Facebook page inbox, including pages connected later."""
    bot = next((b for b in client.list_agent_bots() if BOT_WEBHOOK in (b.get("outgoing_url") or "")), None)
    if not bot:
        logger.warning("staff sync: no Chatwoot agent bot points at %s; run scripts/setup-agent-bot.py", BOT_WEBHOOK)
        return 0
    inboxes = [i for i in client.list_inboxes() if i.get("channel_type") in BOT_CHANNELS]
    for inbox in inboxes:
        client.set_agent_bot(inbox["id"], bot["id"])
    return len(inboxes)


def plan_branch_inboxes(connections, consultants, ids):
    """Chatwoot inbox id → agent ids of the active consultants of the page's branch. Pure."""
    plan = {}
    for conn in connections:
        if conn.get("status") != "Connected" or not conn.get("branch") or not conn.get("chatwoot_inbox_id"):
            continue
        agents = sorted(ids[c["email"]] for c in consultants
                        if c.get("active", 1) and c.get("branch") == conn["branch"] and c["email"] in ids)
        if agents:
            plan.setdefault(int(conn["chatwoot_inbox_id"]), set()).update(agents)
    return {inbox: sorted(agents) for inbox, agents in plan.items()}


def sync_branch_inboxes(client, plan):
    for inbox_id, agent_ids in plan.items():
        client.add_inbox_members(inbox_id, agent_ids)
    return len(plan)


def sync(client, consultants, branches):
    ids = ensure_agents(client, consultants)
    teams = sync_teams(client, consultants, ids, branches)
    return ids, {"agents": len(ids), "teams": teams, "inboxes": sync_inboxes(client)}


def admin_client():
    conf = frappe.conf
    if not conf.get("chatwoot_api_token"):
        return None
    return ChatwootClient(conf.get("chatwoot_api_url") or "http://chatwoot-rails:3000",
                          conf.get("chatwoot_api_token"), int(conf.get("chatwoot_account_id") or 1))


def sync_all():
    client = admin_client()
    if not client:
        logger.info("staff sync skipped: chatwoot_api_token is not configured")
        return None
    rows = frappe.get_all("Consultant", fields=["name", "full_name", "branch", "handles_b2b", "active",
                                                "chatwoot_agent_id", "chatwoot_access_token"])
    consultants = [{**r, "email": r.name} for r in rows]
    ids, counts = sync(client, consultants, frappe.get_all("CRM Territory", pluck="name"))
    connections = frappe.get_all("Channel Connection", fields=["status", "branch", "chatwoot_inbox_id"])
    counts["branch_inboxes"] = sync_branch_inboxes(client, plan_branch_inboxes(connections, consultants, ids))
    for r in rows:
        if r.name in ids and r.chatwoot_agent_id != ids[r.name]:
            frappe.db.set_value("Consultant", r.name, "chatwoot_agent_id", ids[r.name], update_modified=False)
    counts["tokens"] = store_tokens(frappe.conf, [r for r in rows if r.name in ids])
    frappe.db.commit()
    return counts


def needs_token(row):
    """An active consultant with a Chatwoot agent but no stored own token. Pure."""
    return bool(row.get("active") and not row.get("chatwoot_access_token"))


def store_tokens(conf, rows):
    """Each consultant's own Chatwoot token, so answers from a Lead's Messages tab go out under their name
    (mmm_custom.lead_chat). Needs the Platform App token that scripts/configure-chatwoot.py writes."""
    platform_token = conf.get("chatwoot_platform_token")
    if not platform_token:
        return 0
    from frappe.utils.password import set_encrypted_password

    from mmm_custom.chatwoot_client import platform_user_token

    base, stored = conf.get("chatwoot_api_url") or "http://chatwoot-rails:3000", 0
    for row in filter(needs_token, rows):
        try:
            token = platform_user_token(base, platform_token, row.get("full_name") or row["name"], row["name"])
        except Exception:
            logger.exception("chatwoot token fetch failed for %s", row["name"])
            continue
        if token:
            # db-level writes: saving the Consultant would enqueue this sync again (doc_events on_update)
            set_encrypted_password("Consultant", row["name"], token, "chatwoot_access_token")
            frappe.db.set_value("Consultant", row["name"], "chatwoot_access_token", "*" * 8, update_modified=False)
            stored += 1
    return stored


def enqueue_sync(doc=None, method=None):
    frappe.enqueue("mmm_custom.staff_sync.sync_all", queue="short", job_id="mmm_custom_staff_sync",
                   deduplicate=True, enqueue_after_commit=True)


@frappe.whitelist() if frappe else (lambda f: f)
def sync_now():
    frappe.only_for("System Manager")
    return sync_all()
