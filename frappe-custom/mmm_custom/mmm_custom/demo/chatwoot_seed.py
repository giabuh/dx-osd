"""Mirror the demo consultants into Chatwoot (agents, one team per branch + B2B + central, bot on every
Facebook page inbox) through the regular CRM → Chatwoot staff sync.

Run: bench --site crm.localhost execute mmm_custom.demo.chatwoot_seed.run   (after mmm_custom.demo.loader.load)
"""

from mmm_custom.staff_sync import sync_all


def run():
	return sync_all()
