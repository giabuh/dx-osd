from mmm_custom.lifecycle import migrate


def execute():
	# D-116 / D-117: training-centre Lead statuses, registration Deal statuses, lost reasons, existing records moved.
	migrate()
