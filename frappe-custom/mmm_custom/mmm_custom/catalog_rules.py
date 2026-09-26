"""Pure validation rules for the lead-engine catalog DocTypes (no frappe import, unit-tested offline)."""


def assert_leaf_branch(branch, is_group):
	if not branch:
		return
	group = is_group(branch)
	if group is None:
		raise ValueError(f"Unknown branch {branch}")
	if group:
		raise ValueError(f"{branch} is an area, choose a branch")


def validate_promotion(discount_type, discount_value, valid_from, valid_to):
	if not discount_value or discount_value <= 0:
		raise ValueError("Discount must be greater than 0")
	if discount_type == "Percent" and discount_value > 100:
		raise ValueError("A percent discount cannot exceed 100")
	if valid_from and valid_to and valid_to < valid_from:
		raise ValueError("Valid to is before valid from")
