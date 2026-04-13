import frappe
import re
from frappe.utils import now_datetime, add_to_date, format_date, format_time

DEFAULT_EXCLUDE = {
    "name", "owner", "creation", "modified", "modified_by",
    "docstatus", "idx", "_user_tags", "_comments", "_assign",
    "_liked_by", "amended_from"
}

LAYOUT_FIELD_TYPES = {
    "Section Break", "Column Break", "Tab Break", "Fold", "HTML", "Heading"
}

@frappe.whitelist()
def get_my_work_summaries():
    user = frappe.session.user
    cutoff = add_to_date(now_datetime(), hours=12)

    # 1) Find Tasks assigned to this user (via ToDo)
    todo_rows = frappe.get_all(
        "ToDo",
        filters={
            "allocated_to": user,
            "reference_type": "Task",
            "status": ["=", "Open"],  # optional
        },
        fields=["reference_name"],
        limit_page_length=500
    )

    task_names = [r.reference_name for r in todo_rows if r.reference_name]
    if not task_names:
        return []

    # 2) Fetch Task records matching your business filters
    tasks = frappe.get_all(
        "Task",
        filters={
            "name": ["in", task_names],
            "status": ["not in", ["Completed", "Cancelled"]],
            "type": "Work Summary",
            "exp_start_date": ["<=", cutoff],
        },
        fields=[
            "name", "subject", "status", "project", "priority",
            "responsible_contractor", "compliance_status", "work_order_number",
            "parent_task_name", "parent_task",
            "exp_start_date", "exp_end_date", "exp_start_time", "exp_end_time",
            "progress", "project_scope_name", "gameplan_team", "share_folder",
        ],
        order_by="name asc",
        limit_page_length=500
    )

    return tasks

@frappe.whitelist()
def mobile_work_summaries():
    # match your "now + 12h" logic
    cutoff = add_to_date(now_datetime(), hours=12)

    tasks = frappe.get_all(
        "Task",
        filters={
            "status": ["not in", ["Completed", "Cancelled"]],
            "type": "Work Summary",
            "_assign": ["like", f"%{frappe.session.user}%"],
            "exp_start_date": ["<=", cutoff],
        },
        fields=[
            "name", "subject", "status", "project", "priority", "color",
            "responsible_contractor", "compliance_status", "work_order_number",
            "parent_task_name", "parent_task",
            "exp_start_date", "exp_end_date", "exp_start_time", "exp_end_time",
            "progress", "project_scope_name", "gameplan_team", "share_folder",
        ],
        order_by="name asc",
        limit_page_length=500
    )

    # collect parent ids once
    parent_ids = sorted({t.get("parent_task") for t in tasks if t.get("parent_task")})
    parent_progress = {}
    if parent_ids:
        for row in frappe.get_all("Task", filters={"name": ["in", parent_ids]}, fields=["name", "progress"]):
            parent_progress[row["name"]] = row.get("progress") or 0

    grouped = {}
    for t in tasks:
        scope = t.get("project_scope_name") or "Unscoped"
        parent_name = t.get("parent_task_name") or "Ungrouped"
        parent_id = t.get("parent_task")
        t["color"] = t.get("color") or "#CCCCCC"
        t["start_label"] = f'{format_date(t["exp_start_date"], "d MMM")} {format_time(t["exp_start_time"])}'
        t["end_label"]   = f'{format_date(t["exp_end_date"], "d MMM")} {format_time(t["exp_end_time"])}'
        t["date_range"]  = f'{t["start_label"]} – {t["end_label"]}'

        grouped.setdefault(scope, {})
        grouped[scope].setdefault(parent_name, {"parent_task": parent_id, "progress": parent_progress.get(parent_id, 0), "tasks": []})
        grouped[scope][parent_name]["tasks"].append(t)

    # build a stable array for Studio
    scopes = []
    for scope_name, parents in grouped.items():
        parent_groups = []
        for parent_label, payload in parents.items():
            parent_groups.append({
                "label": parent_label,
                "parent_task": payload["parent_task"],
                "progress": payload["progress"],
                "tasks": payload["tasks"],
            })
        scopes.append({"label": scope_name, "parent_groups": parent_groups})

    return {"scopes": scopes}

def doctype_slug(name: str) -> str:
    # safer than replace(" ", "-") — handles multiple spaces/tabs
    return re.sub(r"\s+", "-", (name or "").strip().lower())

@frappe.whitelist()
def list_safety_doctypes(link_task: str) -> list:
    """
    Return an array of actions for Safety doctypes that have
    calendar/gantt enabled. Builds full route including a
    prefilled link_task query param.
    """
    doctypes = frappe.get_all(
        "DocType",
        filters={
            "module": "Safety",
            "istable": 0,
            "is_calendar_and_gantt": 1,
        },
        fields=["name"],
        order_by="name asc",
    )

    actions = []
    for d in doctypes:
        slug = doctype_slug(d["name"])
        route = f"/app/{slug}/new?link_task={link_task}"

        actions.append({
            "label": d["name"],
            "icon": "edit-2",
            "slug": slug,
            "route_link": route,
            "target": "_blank"
        })

    return actions

@frappe.whitelist()
def get_doctype_form_schema(doctype: str="Field Interaction", include_layout: int = 1, include_child_meta: int = 1):
    """
    Returns a UI-friendly schema for rendering a 'New <doctype>' dynamic form in Studio/frappe-ui.

    Query params:
      - doctype (required)
      - include_layout=1/0 (default 1): include section/column/tab breaks in output
      - include_child_meta=1/0 (default 1): include child table field meta
    """
    if not doctype:
        doctype = "Field Interaction"

    if not frappe.db.exists("DocType", doctype):
        frappe.throw(f"Unknown DocType: {doctype}")

    # Basic permission check (you can tighten to 'create' if you're strictly making new docs)
    if not frappe.has_permission(doctype, ptype="read"):
        frappe.throw("Not permitted")

    meta = frappe.get_meta(doctype)

    # Helpful top-level info for a renderer
    out = {
        "doctype": doctype,
        "title_field": meta.title_field,
        "autoname": meta.autoname,
        "naming_rule": meta.naming_rule,
        "is_submittable": int(bool(meta.is_submittable)),
        "is_tree": int(bool(meta.is_tree)),
        "track_changes": int(bool(meta.track_changes)),
        "fields": [],
        "child_tables": {},  # keyed by fieldname of Table field
    }

    def normalize_options(df):
        opt = df.options or ""
        if not isinstance(opt, str):
            return opt

        # Only normalise option strings for these fieldtypes
        if df.fieldtype in ("Select", "MultiSelect", "Autocomplete"):
            # split on any newline type, trim each line, drop blanks
            lines = [line.strip() for line in opt.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
            lines = [line for line in lines if line]  # remove empty lines
            return "\n".join(lines)

        return opt
    
    def options_to_label_value_list(raw: str):
        if not raw or not isinstance(raw, str):
            return []

        # normalise newlines, trim, drop blanks
        lines = [s.strip() for s in raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
        lines = [s for s in lines if s]

        return [{"label": s, "value": s} for s in lines]


    def field_to_schema(df):
        
        return {
            "fieldname": df.fieldname,
            "label": df.label,
            "fieldtype": df.fieldtype,
            "options": (
                options_to_label_value_list(df.options)
                if df.fieldtype in ("Select", "MultiSelect", "Autocomplete")
                else df.options
            ),
            "reqd": int(bool(df.reqd)),
            "hidden": int(bool(df.hidden)),
            "read_only": int(bool(df.read_only)),
            "default": df.default,
            "description": df.description,

            # Conditional logic (Studio/frappe-ui can interpret these)
            "depends_on": df.depends_on,
            "mandatory_depends_on": df.mandatory_depends_on,
            "read_only_depends_on": df.read_only_depends_on,

            # Common UI hints
            "placeholder": getattr(df, "placeholder", None),
            "precision": getattr(df, "precision", None),
            "length": getattr(df, "length", None),
            "in_list_view": int(bool(getattr(df, "in_list_view", 0))),
            "in_standard_filter": int(bool(getattr(df, "in_standard_filter", 0))),

            # Useful for Link fields + fetch rules
            "fetch_from": getattr(df, "fetch_from", None),
            "link_filters": getattr(df, "link_filters", None),
            "ignore_user_permissions": int(bool(getattr(df, "ignore_user_permissions", 0))),
        }

    for df in meta.fields:
        # Keep layout fields if requested
        if df.fieldtype in LAYOUT_FIELD_TYPES:
            if int(include_layout):
                out["fields"].append(field_to_schema(df))
            continue

        # Skip fields with no fieldname (some layout-ish rows)
        if not df.fieldname:
            continue

        # Skip default system fields
        if df.fieldname in DEFAULT_EXCLUDE:
            continue

        out["fields"].append(field_to_schema(df))

        # Include child table schema for Table fields
        if int(include_child_meta) and df.fieldtype == "Table" and df.options:
            child_doctype = df.options
            if frappe.db.exists("DocType", child_doctype):
                child_meta = frappe.get_meta(child_doctype)
                child_fields = []
                for cdf in child_meta.fields:
                    if cdf.fieldtype in LAYOUT_FIELD_TYPES:
                        if int(include_layout):
                            child_fields.append(field_to_schema(cdf))
                        continue
                    if not cdf.fieldname or cdf.fieldname in DEFAULT_EXCLUDE:
                        continue
                    child_fields.append(field_to_schema(cdf))

                out["child_tables"][df.fieldname] = {
                    "child_doctype": child_doctype,
                    "fields": child_fields
                }

    return out