"""Create the demo consultants as Chatwoot agents, one team per branch + B2B + central, and link ids back.

Run: bench --site crm.localhost execute mmm_custom.demo.chatwoot_seed.run   (after mmm_custom.demo.loader.load)
"""

try:
	import frappe
except ImportError:  # offline tests
	frappe = None

from mmm_custom.chatwoot_client import ChatwootClient
from mmm_custom.demo.loader import load_dataset

from mmm_custom.engine.routing import B2B_TEAM, CENTRAL_TEAM


def plan_teams(consultants):
	teams = {}
	for c in consultants:
		team = c["branch"] or (B2B_TEAM if c.get("handles_b2b") else CENTRAL_TEAM)
		teams.setdefault(team, []).append(c["email"])
	return teams


def ensure_agents(client, consultants):
	existing = {a["email"]: a["id"] for a in client.list_agents()}
	ids = {}
	for c in consultants:
		if c["email"] not in existing:
			existing[c["email"]] = client.create_agent(c["full_name"], c["email"])["id"]
		ids[c["email"]] = existing[c["email"]]
	return ids


def run():
	conf = frappe.conf
	client = ChatwootClient(conf.get("chatwoot_api_url") or "http://chatwoot-rails:3000",
	                        conf.get("chatwoot_api_token"), int(conf.get("chatwoot_account_id") or 1))
	consultants = load_dataset()["consultants"]
	ids = ensure_agents(client, consultants)
	teams = {t["name"].lower(): t["id"] for t in client.list_teams()}  # Chatwoot stores team names lowercased
	plan = plan_teams(consultants)
	for name, emails in plan.items():
		if name.lower() not in teams:
			teams[name.lower()] = client.create_team(name)["id"]
		client.add_team_members(teams[name.lower()], [ids[e] for e in emails])
	for inbox in client.list_inboxes():
		if inbox.get("channel_type") == "Channel::FacebookPage":
			client.add_inbox_members(inbox["id"], list(ids.values()))
	for email, agent_id in ids.items():
		frappe.db.set_value("Consultant", email, "chatwoot_agent_id", agent_id)
	frappe.db.commit()
	return {"agents": len(ids), "teams": len(plan)}
