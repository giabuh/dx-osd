from mmm_custom.pages import backfill, ensure_list_column
from mmm_custom.setup import create_catalog_fields


def execute():
	# Patches run before after_migrate creates the field, so create it here first.
	create_catalog_fields()
	backfill()
	# Once: a column the staff later remove from a view stays removed.
	ensure_list_column()
