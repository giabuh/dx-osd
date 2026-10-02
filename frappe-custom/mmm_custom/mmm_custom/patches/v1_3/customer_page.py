from mmm_custom.setup import create_catalog_fields, link_goal_level_slots, update_crm_fields_layout, \
	update_lead_side_panel


def execute():
	# D-122: the customer page's grouped side panel, without the organization field.
	# D-123: learner name, learning goal and current level on the Lead; the bot's goal / level slots fill them.
	create_catalog_fields()
	update_crm_fields_layout()
	update_lead_side_panel()
	link_goal_level_slots()
