"""Pure validation rules for the lead-engine catalog DocTypes (no frappe import, unit-tested offline)."""


def assert_leaf_branch(branch, is_group):
	if not branch:
		return
	group = is_group(branch)
	if group is None:
		raise ValueError(f"Unknown branch {branch}")
	if group:
		raise ValueError(f"{branch} is an area, choose a branch")
