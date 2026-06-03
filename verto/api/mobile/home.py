import frappe
from frappe.utils import add_to_date, now_datetime


GENERIC_FORM_BUTTONS = [
    {"label": "LV Pre-Start", "doctype": "LV Pre-Start"},
    {"label": "Take 5", "doctype": "Take 5"},
    {"label": "Shift Request", "doctype": "Shift Request"},
    {"label": "Leave Application", "doctype": "Leave Application"},
    {"label": "Personal Fatigue Assessment", "doctype": "Personal Fatigue Assessment"},
]


TASK_FORM_BUTTONS = [
    {"label": "Commitment Interaction", "doctype": "Commitment Interaction"},
    {"label": "Contractor Management Audit Checklist", "doctype": "Contractor Management Audit Checklist"},
    {"label": "Field Interaction", "doctype": "Field Interaction"},
    {"label": "Job Hazard Analysis Review", "doctype": "Job Hazard Analysis Review"},
    {"label": "Prohibited and Restricted Tooling Checklist", "doctype": "Prohibited and Restricted Tooling Checklist"},
    {"label": "Safety Identification Rectification", "doctype": "Safety Identification Rectification"},
    {"label": "Supervisor BATB", "doctype": "Supervisor BATB"},
    {"label": "Weekly Summary", "doctype": "Weekly Summary"},
    {"label": "Workplace Inspection", "doctype": "Workplace Inspection"},
]


CCV_BUTTONS = [
    {"label": "CCV - Confined Space", "doctype": "CCV - Confined Space"},
    {"label": "CCV - Contact with Electricity", "doctype": "CCV - Contact with Electricity"},
    {"label": "CCV - Dropped Objects", "doctype": "CCV - Dropped Objects"},
    {"label": "CCV - Entanglement and Crushing", "doctype": "CCV - Entanglement and Crushing"},
    {"label": "CCV - Fall From Height", "doctype": "CCV - Fall From Height"},
    {"label": "CCV - Hot Works", "doctype": "CCV - Hot Works"},
    {"label": "CCV - Lifting Operations", "doctype": "CCV - Lifting Operations"},
    {"label": "CCV - Uncontrolled Release of Energy", "doctype": "CCV - Uncontrolled Release of Energy"},
    {"label": "CCV - Vehicles and Mobile Equipment", "doctype": "CCV - Vehicles and Mobile Equipment"},
    {"label": "CCV - Working Near Water", "doctype": "CCV - Working Near Water"},
]


def require_login():
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.PermissionError)


def scrub_mobile_doctype(doctype):
    return (doctype or "").strip().lower().replace(" ", "-")


def doctype_exists(doctype):
    return bool(frappe.db.exists("DocType", doctype))


def allowed_button(button):
    doctype = button.get("doctype")

    if not doctype_exists(doctype):
        return None

    if not frappe.has_permission(doctype, "create"):
        return None

    return {
        "label": button.get("label") or doctype,
        "doctype": doctype,
        "mobile_doctype": scrub_mobile_doctype(doctype),
    }


def get_allowed_buttons(buttons):
    allowed = []

    for button in buttons:
        item = allowed_button(button)
        if item:
            allowed.append(item)

    return allowed


def get_handover_base():
    user_roles = frappe.get_roles(frappe.session.user)

    if "Lead HSE Advisor" in user_roles or "System Manager" in user_roles:
        return "/app/lead-safety-handover"

    return "/app/safety-handover"


def get_task_fields():
    fields = [
        "name",
        "subject",
        "status",
        "project",
        "priority",
        "responsible_contractor",
        "compliance_status",
        "parent_task_name",
        "parent_task",
        "exp_start_date",
        "exp_end_date",
        "exp_start_time",
        "exp_end_time",
        "progress",
        "project_scope_name",
    ]

    meta = frappe.get_meta("Task")
    fieldnames = {df.fieldname for df in meta.fields}

    optional_fields = [
        "work_order_number",
        "gameplan_team",
        "share_folder",
    ]

    for fieldname in optional_fields:
        if fieldname in fieldnames:
            fields.append(fieldname)

    return fields


def get_project_fields():
    fields = [
        "name",
        "status",
    ]

    meta = frappe.get_meta("Project")
    fieldnames = {df.fieldname for df in meta.fields}

    optional_fields = [
        "gameplan_team_name",
        "gameplan_project",
        "raven_channel",
        "raven_workspace",
        "roster_or_shutdown",
        "customer",
    ]

    for fieldname in optional_fields:
        if fieldname in fieldnames:
            fields.append(fieldname)

    return fields


def get_customer_fields():
    fields = ["name"]

    meta = frappe.get_meta("Customer")
    fieldnames = {df.fieldname for df in meta.fields}

    optional_fields = [
        "image",
        "customer_name",
    ]

    for fieldname in optional_fields:
        if fieldname in fieldnames:
            fields.append(fieldname)

    return fields


def fetch_assigned_work_summary_tasks():
    user = frappe.session.user
    next_12_hours = add_to_date(now_datetime(), hours=12)

    return frappe.get_all(
        "Task",
        filters={
            "status": ["not in", ["Completed", "Cancelled"]],
            "type": "Work Summary",
            "_assign": ["like", f"%{user}%"],
            "exp_start_date": ["<=", next_12_hours],
        },
        fields=get_task_fields(),
        limit_start=0,
        limit_page_length=500,
        order_by="name asc",
    )


def fetch_customer_details_for_projects(projects):
    customer_names = list({
        project.get("customer")
        for project in projects
        if project.get("customer")
    })

    if not customer_names:
        return {}

    customers = frappe.get_all(
        "Customer",
        filters={
            "name": ["in", customer_names],
        },
        fields=get_customer_fields(),
        limit_start=0,
        limit_page_length=500,
        order_by="name asc",
    )

    return {customer.name: customer for customer in customers}


def fetch_projects_for_tasks(tasks):
    project_names = list({
        task.get("project")
        for task in tasks
        if task.get("project")
    })

    if not project_names:
        return {}

    projects = frappe.get_all(
        "Project",
        filters={
            "name": ["in", project_names],
        },
        fields=get_project_fields(),
        limit_start=0,
        limit_page_length=500,
        order_by="name asc",
    )

    customer_map = fetch_customer_details_for_projects(projects)

    project_map = {}

    for project in projects:
        customer = project.get("customer")
        customer_details = customer_map.get(customer, {})

        project["customer_name"] = customer_details.get("customer_name") or customer
        project["customer_image"] = customer_details.get("image")

        project_map[project.name] = project

    return project_map


def fetch_parent_progress(grouped):
    parent_names = set()

    for scope in grouped:
        for parent_group in scope.get("parent_groups", []):
            if parent_group.get("parent_task"):
                parent_names.add(parent_group.get("parent_task"))

    if not parent_names:
        return {}

    rows = frappe.get_all(
        "Task",
        filters={
            "name": ["in", list(parent_names)],
        },
        fields=["name", "progress"],
        limit_page_length=500,
    )

    return {row.name: row.progress for row in rows}


def group_tasks(tasks, project_map):
    grouped_map = {}

    for task in tasks:
        scope_name = task.get("project_scope_name") or "Unscoped Work"
        parent_task_name = task.get("parent_task_name") or "Other Tasks"
        parent_task = task.get("parent_task")
        project_name = task.get("project")
        project = project_map.get(project_name, {})

        if scope_name not in grouped_map:
            grouped_map[scope_name] = {
                "scope_name": scope_name,
                "project": project_name,
                "project_details": project,
                "parent_groups": {},
            }

        if parent_task_name not in grouped_map[scope_name]["parent_groups"]:
            grouped_map[scope_name]["parent_groups"][parent_task_name] = {
                "parent_task_name": parent_task_name,
                "parent_task": parent_task,
                "progress": 0,
                "project": project_name,
                "project_details": project,
                "tasks": [],
            }

        grouped_map[scope_name]["parent_groups"][parent_task_name]["tasks"].append(task)

    grouped = []

    for scope in grouped_map.values():
        parent_groups = list(scope["parent_groups"].values())
        scope["parent_groups"] = parent_groups
        grouped.append(scope)

    progress_map = fetch_parent_progress(grouped)

    for scope in grouped:
        for parent_group in scope["parent_groups"]:
            parent_task = parent_group.get("parent_task")
            parent_group["progress"] = progress_map.get(parent_task, 0)

    return grouped


@frappe.whitelist()
def get_home_summary():
    require_login()

    tasks = fetch_assigned_work_summary_tasks()
    project_map = fetch_projects_for_tasks(tasks)
    grouped_tasks = group_tasks(tasks, project_map)

    return {
        "user": frappe.session.user,
        "handover_base": get_handover_base(),
        "grouped_tasks": grouped_tasks,
        "generic_forms": get_allowed_buttons(GENERIC_FORM_BUTTONS),
        "task_forms": get_allowed_buttons(TASK_FORM_BUTTONS),
        "ccv_forms": get_allowed_buttons(CCV_BUTTONS),
        "raven_base": "https://dashboard.minesitesupport.com.au/raven",
    }