app_name = "mmm_custom"
app_title = "MMM Custom"
app_publisher = "MMM"
app_description = "Chatwoot-CRM integration custom fields"
app_email = "baoluu674@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
add_to_apps_screen = [{
    "name": "mmm_custom",
    "logo": "/assets/mmm_custom/images/bot.svg",
    "title": "Quản trị",
    "route": "/crm/admin",
    "has_permission": "mmm_custom.desk.can_open_bot",
}]

# The manager screens live in the CRM frontend (/crm/admin). The old standalone pages redirect there;
# browsers keep an old #tab fragment, which the CRM page turns into that tab.
website_redirects = [{"source": "/bot", "target": "/crm/admin"}, {"source": "/admin", "target": "/crm/admin"}]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/mmm_custom/css/mmm_custom.css"
# app_include_js = "/assets/mmm_custom/js/mmm_custom.js"

# include js, css files in header of web template
# web_include_css = "/assets/mmm_custom/css/mmm_custom.css"
# web_include_js = "/assets/mmm_custom/js/mmm_custom.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "mmm_custom/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
doctype_js = {"CRM Product": "public/js/crm_product.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "mmm_custom/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "mmm_custom.utils.jinja_methods",
# 	"filters": "mmm_custom.utils.jinja_filters"
# }

# Installation
# ------------

after_install = "mmm_custom.setup.create_custom_field_and_lead_sources"
# Catalog custom fields are declared in setup.CATALOG_FIELDS; re-applied on every migrate so new ones land without a patch.
after_migrate = ["mmm_custom.setup.create_catalog_fields", "mmm_custom.sources.ensure_sources",
                 "mmm_custom.referral.backfill", "mmm_custom.setup.update_crm_fields_layout",
                 "mmm_custom.desk.hide_unused_workspaces",
                 "mmm_custom.desk.remove_old_bot_workspace", "mmm_custom.desk.ensure_bot_workspace_icon",
                 "mmm_custom.desk.apply_default_apps", "mmm_custom.crm_links.ensure_lead_form_script"]

# Lead engine (spec 2026-09-26-edu-lead-engine): any edit to catalog, slot, skill or settings data
# clears the engine's cached catalog snapshot so the next customer message sees it.
_LEAD_ENGINE_DATA = ("Course Group", "CRM Product", "CRM Territory", "Bot Slot", "Bot Skill", "Lead Engine Settings")
doc_events = {
	dt: {"on_update": "mmm_custom.engine.repo.clear_catalog_cache", "on_trash": "mmm_custom.engine.repo.clear_catalog_cache"}
	for dt in _LEAD_ENGINE_DATA
}
# Learning signal: a person corrected the branch/course the bot set on a Lead (D-057).
doc_events["CRM Lead"] = {"on_update": "mmm_custom.engine.learning.on_lead_update",
                          # Referral codes (D-103)
                          "before_insert": "mmm_custom.referral.set_code",
                          "validate": "mmm_custom.referral.resolve_referrer"}
# Landing page by role: managers on /crm/admin, everyone else on /crm (mmm_custom.desk.default_app_for).
doc_events["User"] = {"on_update": "mmm_custom.desk.apply_user_default_app"}
# Staff live in CRM; Chatwoot agents/teams follow (mmm_custom.staff_sync).
doc_events["Consultant"] = {"on_update": "mmm_custom.staff_sync.enqueue_sync",
                            "on_trash": "mmm_custom.staff_sync.enqueue_sync"}

# Template filters for bot copy: {{ course.fee | vnd }} → "1.800.000đ", {{ s.date | date_vi }} → "Thứ 7, 04/10".
jinja = {"filters": ["mmm_custom.engine.render.vnd", "mmm_custom.engine.render.date_vi"]}

# Other apps subscribe to engine events with their own `lead_engine_events` hook (see engine/events.py).

# [I] AI follow-up agent: 08:00 site time, so salespeople find the Tasks when their day starts.
# It does nothing unless the site config has typesafe_api_key.
# Autopilot publisher: runs every 5 minutes to publish scheduled Facebook posts.
scheduler_events = {
	"cron": {
		"0 8 * * *": ["mmm_custom.followup.run_daily"],
		# Heals failed staff syncs and gives newly connected Facebook pages the bot.
		"*/10 * * * *": ["mmm_custom.staff_sync.sync_all"],
		"*/5 * * * *": ["mmm_custom.autopilot.publish_scheduled_posts"],
	},
	# AI Decision Log retention (Lead Engine Settings.log_retention_days, default 180).
	"daily": ["mmm_custom.engine.log.purge_old_logs"],
}


# Uninstallation
# ------------

# before_uninstall = "mmm_custom.uninstall.before_uninstall"
# after_uninstall = "mmm_custom.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "mmm_custom.utils.before_app_install"
# after_app_install = "mmm_custom.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "mmm_custom.utils.before_app_uninstall"
# after_app_uninstall = "mmm_custom.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "mmm_custom.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["mmm_custom.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------
# (See scheduler_events defined above with 08:00 followup and */5 autopilot publisher)


# Testing
# -------

# before_tests = "mmm_custom.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "mmm_custom.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "mmm_custom.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["mmm_custom.utils.before_request"]
# after_request = ["mmm_custom.utils.after_request"]

# Job Events
# ----------
# before_job = ["mmm_custom.utils.before_job"]
# after_job = ["mmm_custom.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"mmm_custom.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
