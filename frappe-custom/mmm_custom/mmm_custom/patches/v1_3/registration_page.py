from mmm_custom.enrolment import update_deal_layouts
from mmm_custom.setup import create_catalog_fields


def execute():
	# D-123: who studies on the registration; the side panel gets the learner section (and the page its class card
	# and fee progress, D-122).
	create_catalog_fields()
	update_deal_layouts()
