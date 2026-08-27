app_name = "verto"
app_title = "Verto"
app_publisher = "Webwire"
app_description = "Fully customised Verto application for ERPNext Version-16"
app_email = "support@webwire.com.au"
app_license = "apache-2.0"
app_logo = "/assets/verto/images/marketplace-logo.png"
app_logo_url = "/assets/verto/images/marketplace-logo.png"

required_apps = ["erpnext", "hrms", "raven", "gameplan"]

add_to_apps_screen = [
    {
        "name": "verto",
        "logo": "/assets/verto/images/marketplace-logo.png",
        "title": "Verto Planner",
        "route": "/planner",
        "has_permission": "verto.access.can_view_planner_app",
    },
    {
        "name": "verto_mobile",
        "logo": "/assets/verto/images/marketplace-logo.png",
        "title": "Verto Mobile",
        "route": "/verto-mobile",
        "has_permission": "verto.access.can_view_mobile_app",
    },
]

app_include_css = [
    "/assets/verto/css/verto.css",
    "/assets/verto/css/leaflet.css",
    "/assets/verto/css/leaflet.draw.css",
    "/assets/verto/css/easy-button.css",
    "/assets/verto/css/L.Control.Locate.css",
]

app_include_js = [
    "/assets/verto/js/gantt_view.js",
    "/assets/verto/js/task_gantt_map.js",
    "/assets/verto/js/map_defaults.js",
    "/assets/verto/js/project_calendar.js",
    "/assets/verto/js/map_view.js",
    "/assets/verto/js/raven_peri_auto_command.js",
]

web_include_js = [
    "/assets/verto/js/raven_peri_auto_command.js",
]
web_include_css = []

website_context = {
    "include_js": [
        "/assets/verto/js/raven_peri_auto_command.js",
    ]
}

doctype_js = {
    "Employee": "public/js/employee.js",
}

# Installation / migration hardening
# ----------------------------------
after_install = "verto.install.after_install"
after_migrate = "verto.install.after_migrate"
after_app_install = "verto.optional_integrations.after_app_install"

extend_bootinfo = ["verto.api.mobile.boot.add_map_settings_to_boot"]

# Apply site-managed runtime configuration before normal web and worker code.
# This removes the need to manually duplicate Verto settings into site_config.json.
before_request = ["verto.runtime_config.apply_runtime_config"]
before_job = ["verto.runtime_config.apply_runtime_config"]

# Document events
# ---------------
doc_events = {
    "Verto Mobile Settings": {
        "on_update": "verto.install.refresh_mobile_settings_configuration",
    },
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
    },
}

# Scheduled tasks
# ---------------
scheduler_events = {
    "daily": [
        "verto.api.qualifications.refresh_qualification_statuses",
        "verto.api.qualifications.send_qualification_expiry_notifications",
    ],
    "cron": {
        "0 09 * * *": [
            "verto.api.mobile.push_notifications.send_previous_day_missing_hours_reminders",
        ],
        "0 10 * * *": [
            "verto.api.automate.send_weekly_timesheet_verification",
        ],
        "0 12 * * *": [
            "verto.api.automate.send_grouped_timesheet_followup_reminders",
        ],
        "0 13 * * *": [
            "verto.api.automate.send_grouped_weekly_timesheets",
        ],
    },
}

override_whitelisted_methods = {
    "frappe.geo.utils.get_coords": "verto.geo.utils.verto_get_coords",
}

# Serve /verto-mobile-sw.js through Frappe rather than an nginx alias.
page_renderer = ["verto.pwa.VertoServiceWorkerRenderer"]

website_route_rules = [
    {"from_route": "/verto-mobile/<path:app_path>", "to_route": "verto-mobile"},
    {"from_route": "/planner/<path:app_path>", "to_route": "planner"},
]
