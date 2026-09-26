from mmm_custom.setup import create_custom_fields, update_crm_fields_layout


def execute():
	# Existing sites already ran create_custom_field_and_lead_sources; this adds the AI fields.
	create_custom_fields()
	update_crm_fields_layout()
