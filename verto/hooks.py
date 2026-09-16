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
    "/assets/verto/css/whiteboard.css",
    "/assets/verto/css/excalidraw.css",
]

app_include_js = [
    "/assets/verto/js/gantt_view.js",
    "/assets/verto/js/task_gantt_map.js",
    "/assets/verto/js/map_defaults.js",
    "/assets/verto/js/geolocation.js",
    "/assets/verto/js/project_calendar.js",
    "/assets/verto/js/map_view.js",
    "/assets/verto/js/raven_peri_auto_command.js",
    "/assets/verto/js/whiteboard_custom.js",
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
after_install = [
    "verto.install.after_install",
    "verto.api.mobile.peri_voice_settings.after_install",
    "verto.api.mobile.voice_jha_print.after_install",
    "verto.api.mobile.global_notifications.after_install",
]
after_migrate = [
    "verto.install.after_migrate",
    "verto.api.mobile.peri_voice_settings.after_migrate",
    "verto.api.mobile.voice_jha_print.after_migrate",
    "verto.api.mobile.global_notifications.after_migrate",
    "verto.api.mobile.home_child_tasks.sync_active_jha_planned_steps",
]
after_app_install = "verto.optional_integrations.after_app_install"

extend_bootinfo = ["verto.api.mobile.boot.add_map_settings_to_boot"]

# Apply site-specific runtime configuration before normal web and worker code.
# This removes the need to manually duplicate Verto settings into site_config.json.
before_request = [
    "verto.runtime_config.apply_runtime_config",
    "verto.default_apps.configure_default_apps",
]
before_job = ["verto.runtime_config.apply_runtime_job_config"]

# Password login can create its session before before_request hooks run.
on_session_creation = "verto.default_apps.configure_default_apps"

extend_doctype_class = {
    "User": ["verto.default_apps.VertoDefaultAppMixin"],
}

# Permissions
# -----------
permission_query_conditions = {
    "Digital Job Hazard Analysis": "verto.api.mobile.voice_jha_permissions.get_permission_query_conditions",
}

has_permission = {
    "Digital Job Hazard Analysis": "verto.api.mobile.voice_jha_permissions.has_permission",
}

# Document events
# ---------------
doc_events = {
    "Verto Mobile Settings": {
        "on_update": "verto.install.refresh_mobile_settings_configuration",
    },
    "Task": {
        "before_validate": "verto.api.mobile.task_checklist.sync_task_checklist_progress",
        "on_update": "verto.safety.doctype.digital_job_hazard_analysis.digital_job_hazard_analysis.mark_linked_jhas_for_work_change",
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

# Merge with existing document hooks so live updates also include Desk, mobile,
# imports and background jobs. on_change includes Document.db_set operations.
from verto.api.planner_realtime import DOCTYPE_SCOPES as _planner_doctype_scopes

for _doctype in _planner_doctype_scopes:
    _events = doc_events.setdefault(_doctype, {})
    for _event in ("after_insert", "on_update", "on_submit", "on_cancel", "on_update_after_submit", "on_change", "after_delete", "after_rename"):
        _existing = _events.get(_event, [])
        if isinstance(_existing, str):
            _existing = [_existing]
        _events[_event] = [*_existing, "verto.api.planner_realtime.document_changed"]

# Scheduled tasks
# ---------------
scheduler_events = {
    "hourly": [
        "verto.api.mobile.ai_photo_analysis.retry_failed_reviews",
    ],
    "daily": [
        "verto.api.qualifications.refresh_qualification_statuses",
        "verto.api.qualifications.send_qualification_expiry_notifications",
    ],
    "cron": {
        "0 08 * * *": [
            "verto.api.mobile.global_notifications.send_project_missing_purchase_order_reminders",
        ],
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

# Retain global-notification de-duplication records long enough to cover audits
# without allowing the delivery table to grow forever.
default_log_clearing_doctypes = {
    "Verto Global Notification Log": 180,
}

override_whitelisted_methods = {
    "frappe.apps.get_apps": "verto.default_apps.get_apps",
    "frappe.apps.set_app_as_default": "verto.default_apps.set_app_as_default",
    "frappe.geo.utils.get_coords": "verto.geo.utils.verto_get_coords",
    "verto.api.mobile.home.get_home_summary": "verto.api.mobile.home_child_tasks.get_home_summary",
    "verto.api.mobile.voice_jha.get_voice_jha_bootstrap": "verto.api.mobile.voice_jha_phase2.get_voice_jha_bootstrap",
    "verto.api.mobile.voice_jha.create_voice_jha_draft": "verto.api.mobile.voice_jha_phase2.create_voice_jha_draft",
    "verto.api.mobile.voice_jha.start_voice_jha_call": "verto.api.mobile.voice_jha_facilitator.start_voice_jha_call",
    "verto.api.mobile.voice_jha_tools.execute_voice_jha_tool": "verto.api.mobile.voice_jha_tools_streamlined.execute_voice_jha_tool",
}

# Serve site-specific install metadata and the root worker through Frappe.
page_renderer = [
    "verto.pwa.VertoManifestRenderer",
    "verto.pwa.VertoServiceWorkerRenderer",
]

website_route_rules = [
    {"from_route": "/verto-mobile/<path:app_path>", "to_route": "verto-mobile"},
    {"from_route": "/planner/<path:app_path>", "to_route": "planner"},
]
