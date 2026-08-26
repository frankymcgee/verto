app_name = "verto"
app_title = "Verto"
app_publisher = "Webwire"
app_description = "Fully customised Verto application for ERPNext Version-16"
app_email = "support@webwire.com.au"
app_license = "apache-2.0"
# Apps
# ------------------

required_apps = ["erpnext", "hrms", "raven", "gameplan"]

# Each item in the list will be shown as an app in the apps page
add_to_apps_screen = [
	{
		"name": "Planner",
 		"logo": "/assets/verto/images/verto.png",
 		"title": "Planner",
 		"route": "/planner",
 		"has_permission": "verto.api.planner.check_app_permission"
 	}
 ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = [
	"/assets/verto/css/verto.css",
    "/assets/verto/css/leaflet.css",
    "/assets/verto/css/leaflet.draw.css",
    "/assets/verto/css/easy-button.css",
    "/assets/verto/css/L.Control.Locate.css"
]
app_include_js = [
	"/assets/verto/js/gantt_view.js",
    "/assets/verto/js/task_gantt_map.js",
	#"/assets/verto/js/geolocation.js",
	"/assets/verto/js/map_defaults.js",
	"/assets/verto/js/project_calendar.js",
	"/assets/verto/js/map_view.js",
    #"/assets/verto/js/leaflet.js",
    #"/assets/verto/js/leaflet.draw.js",
    #"/assets/verto/js/easy-button.js",
    #"/assets/verto/js/L.Control.Locate.js"
    "/assets/verto/js/raven_peri_auto_command.js",
]	

# include js, css files in header of web template
web_include_js = [
    #"/assets/verto/js/mobile_install_prompt.js",
    "/assets/verto/js/raven_peri_auto_command.js",
]

web_include_css = [
    #"/assets/verto/css/mobile_install_prompt.css"
]

website_context = {
    "include_js": [
        "/assets/verto/js/raven_peri_auto_command.js",
    ]
}

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "verto/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

doctype_js = {
	"Employee": "public/js/employee.js",
}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "verto/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
#	"methods": "verto.utils.jinja_methods",
#	"filters": "verto.utils.jinja_filters"
# }

# Installation
# ------------

after_install = "verto.install.after_install"
after_migrate = "verto.install.after_migrate"

# Uninstallation
# ------------

# before_uninstall = "verto.uninstall.before_uninstall"
# after_uninstall = "verto.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "verto.utils.before_app_install"
# after_app_install = "verto.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "verto.utils.before_app_uninstall"
# after_app_uninstall = "verto.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "verto.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
#	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
#	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
#     "Shift Schedule Assignment": "verto.overrides.shift_schedule_assignment.CustomShiftScheduleAssignment"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	# "*": {
	# 	"on_update": "method",
	# 	"on_cancel": "method",
	# 	"on_trash": "method"
    # }
    "Task": {
        "before_validate": "verto.api.mobile.task_checklist.sync_task_checklist_progress",
    },
    "Employee": {
        "before_validate": "verto.api.qualifications.validate_employee_qualifications",
    },
    "Project": {
        "after_insert": "verto.api.hooks.create_project_handover_records",
        "on_update": "verto.api.hooks.create_project_handover_records",
    },
    "Raven Message": {
        "after_insert": [
            "verto.api.mobile.push_notifications.notify_project_chat_message",
            "verto.api.mobile.raven_realtime_bridge.publish_raven_message_upsert",
        ],
        "on_update": "verto.api.mobile.raven_realtime_bridge.publish_raven_message_upsert",
        "after_delete": "verto.api.mobile.raven_realtime_bridge.publish_raven_message_delete",
    },
    "Shift Assignment": {
        "on_submit": "verto.api.mobile.push_notifications.notify_shift_assigned",
        "on_update_after_submit": "verto.api.mobile.push_notifications.notify_shift_changed",
    },
    "ToDo": {
        "after_insert": "verto.api.mobile.push_notifications.notify_document_assignment",
    }
}

# Scheduled Tasks
# ---------------

scheduler_events = {
#	"all": [
#		"verto.tasks.all"
#	],
    "daily": [
        "verto.api.qualifications.refresh_qualification_statuses",
        "verto.api.qualifications.send_qualification_expiry_notifications",
    ],
    # "hourly": [
    #     "verto.jobs.hourly.escalate_overdue_actions",
    # ],
#	"weekly": [
#		"verto.tasks.weekly"
#	],
#	"monthly": [
#		"verto.tasks.monthly"
#	],
    "cron": {
        "0 09 * * *": [
            "verto.api.mobile.push_notifications.send_previous_day_missing_hours_reminders",
        ],
        "0 10 * * *": [
            "verto.api.automate.send_weekly_timesheet_verification",
        ],
        "0 13 * * *": [
            "verto.api.automate.send_grouped_weekly_timesheets"
        ],
        "0 12 * * *": [
            "verto.api.automate.send_grouped_timesheet_followup_reminders"
        ]
    }
}

# Testing
# -------

# before_tests = "verto.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
#	"frappe.desk.doctype.event.event.get_events": "verto.event.get_events",
# }
override_whitelisted_methods = {
    "frappe.geo.utils.get_coords": "verto.geo.utils.verto_get_coords",
}

#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
#	"Task": "verto.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["verto.utils.before_request"]
# after_request = ["verto.utils.after_request"]

# Job Events
# ----------
# before_job = ["verto.utils.before_job"]
# after_job = ["verto.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
#	{
#		"doctype": "{doctype_1}",
#		"filter_by": "{filter_by}",
#		"redact_fields": ["{field_1}", "{field_2}"],
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_2}",
#		"filter_by": "{filter_by}",
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_3}",
#		"strict": False,
#	},
#	{
#		"doctype": "{doctype_4}"
#	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
#	"verto.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
#	"Logging DocType Name": 30  # days to retain logs
# }

# Custom page renderers
# ---------------------
# Serve the Verto service worker from the site root so no nginx alias is needed.
page_renderer = ["verto.pwa.VertoServiceWorkerRenderer"]

website_route_rules = [
    {"from_route": "/verto-mobile/<path:app_path>", "to_route": "verto-mobile"},
    {"from_route": "/planner/<path:app_path>", "to_route": "planner"},
]
