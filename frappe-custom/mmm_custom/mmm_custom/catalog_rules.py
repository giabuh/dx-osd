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


# Select options of Bot Slot / Bot Skill; the code registries of C2 must use the same values.
SLOT_TYPES = ("catalog", "choice", "phone", "number", "text")
CATALOG_SOURCES = ("course", "branch")
ACTION_TYPES = ("answer_template", "schedule_lookup", "fee_quote", "branch_info", "send_media", "recommend_courses", "handoff")
FOLLOW_UP_TARGETS = ("skill", "slot", "handoff")


def validate_slot_dependency(slot_type, catalog_source, depends_on_slot, depends_on_value):
	if slot_type == "catalog" and not catalog_source:
		raise ValueError("A catalog slot needs a catalog_source")
	if bool(depends_on_slot) != bool(depends_on_value):
		raise ValueError("Set both depends_on_slot and depends_on_value, or neither")
