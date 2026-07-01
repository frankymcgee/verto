import json
from datetime import datetime, timedelta

import frappe
from frappe.utils import getdate, now_datetime, today


ALLOWED_MOBILE_DOCTYPES = {
    "field-interaction": "Field Interaction",
    "commitment-interaction": "Commitment Interaction",
    "workplace-inspection": "Workplace Inspection",
    "job-hazard-analysis-review": "Job Hazard Analysis Review",
    "contractor-management-audit-checklist": "Contractor Management Audit Checklist",
    "prohibited-and-restricted-tooling-checklist": "Prohibited and Restricted Tooling Checklist",
    "safety-identification-rectification": "Safety Identification Rectification",
    "supervisor-batb": "Supervisor BATB",
    "weekly-summary": "Weekly Summary",

    "safety-handover": "Safety Handover",
    "lead-safety-handover": "Lead Safety Handover",

    "lv-pre-start": "LV Pre-Start",
    "take-5": "Take 5",
    "shift-request": "Shift Request",
    "leave-application": "Leave Application",
    "personal-fatigue-assessment": "Personal Fatigue Assessment",

    "daily-timesheet": "Daily Timesheet",

    "ccv---confined-space": "CCV - Confined Space",
    "ccv---contact-with-electricity": "CCV - Contact with Electricity",
    "ccv---dropped-objects": "CCV - Dropped Objects",
    "ccv---entanglement-and-crushing": "CCV - Entanglement and Crushing",
    "ccv---fall-from-height": "CCV - Fall From Height",
    "ccv---hot-works": "CCV - Hot Works",
    "ccv---lifting-operations": "CCV - Lifting Operations",
    "ccv---uncontrolled-release-of-energy": "CCV - Uncontrolled Release of Energy",
    "ccv---vehicles-and-mobile-equipment": "CCV - Vehicles and Mobile Equipment",
    "ccv---working-near-water": "CCV - Working Near Water",
}


SKIP_FIELD_TYPES = {
    "Column Break",
    "Fold",
    "HTML",
    "Button",
    "Image",
    "Heading",
}

READ_ONLY_FIELD_TYPES = {
    "Read Only",
}

SYSTEM_FIELDS = {
    "name",
    "owner",
    "creation",
    "modified",
    "modified_by",
    "docstatus",
    "idx",
    "amended_from",
}


def require_login():
    if frappe.session.user == "Guest":
        frappe.throw("Login required", frappe.PermissionError)


def get_user_full_name():
    return frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user


def normalise_mobile_doctype_key(value):
    value = str(value or "").strip()

    if not value:
        return ""

    # Handles route/API values like:
    # Field%20Interaction, Field+Interaction, field_interaction, field-interaction
    try:
        value = frappe.utils.unquote(value)
    except Exception:
        pass

    value = value.replace("+", " ").strip()

    return frappe.scrub(value).replace("_", "-")


def get_allowed_doctype(mobile_doctype):
    if not mobile_doctype:
        frappe.throw("Mobile DocType is required.", frappe.ValidationError)

    raw_value = str(mobile_doctype or "").strip()

    try:
        decoded_value = frappe.utils.unquote(raw_value).replace("+", " ").strip()
    except Exception:
        decoded_value = raw_value.replace("+", " ").strip()

    normalised_key = normalise_mobile_doctype_key(decoded_value)

    # 1. Standard mobile slug lookup:
    # field-interaction -> Field Interaction
    if normalised_key in ALLOWED_MOBILE_DOCTYPES:
        return ALLOWED_MOBILE_DOCTYPES[normalised_key]

    # 2. Raw key lookup, just in case:
    # field-interaction exactly as provided
    if raw_value in ALLOWED_MOBILE_DOCTYPES:
        return ALLOWED_MOBILE_DOCTYPES[raw_value]

    # 3. Allow actual DocType names if they are in the allowed mobile map:
    # Field Interaction -> Field Interaction
    allowed_doctypes = set(ALLOWED_MOBILE_DOCTYPES.values())

    if decoded_value in allowed_doctypes:
        return decoded_value

    # 4. Allow scrubbed/slugged actual DocType names:
    # field-interaction -> Field Interaction
    for allowed_doctype in allowed_doctypes:
        if normalise_mobile_doctype_key(allowed_doctype) == normalised_key:
            return allowed_doctype

    frappe.throw(
        f"This mobile form is not allowed: {decoded_value}",
        frappe.PermissionError,
    )


def get_mobile_slug_for_doctype(doctype):
    doctype = str(doctype or "").strip()

    for mobile_doctype, mapped_doctype in ALLOWED_MOBILE_DOCTYPES.items():
        if mapped_doctype == doctype:
            return mobile_doctype

    return normalise_mobile_doctype_key(doctype)


def has_desk_create_permission(doctype):
    return bool(frappe.has_permission(doctype, "create"))


def has_desk_read_permission(doc):
    try:
        return bool(doc.has_permission("read"))
    except Exception:
        return bool(frappe.has_permission(doc.doctype, "read", doc=doc))


def has_desk_write_permission(doc):
    try:
        return bool(doc.has_permission("write"))
    except Exception:
        return bool(frappe.has_permission(doc.doctype, "write", doc=doc))


def require_desk_doctype_permission(doctype, permission_type):
    if not frappe.has_permission(doctype, permission_type):
        frappe.throw(
            f"You do not have Desk permission to {permission_type} {doctype}.",
            frappe.PermissionError,
        )


def require_desk_doc_read(doc):
    if not has_desk_read_permission(doc):
        frappe.throw(
            f"You do not have Desk permission to read {doc.doctype} {doc.name}.",
            frappe.PermissionError,
        )


def require_desk_doc_write(doc):
    if not has_desk_write_permission(doc):
        frappe.throw(
            f"You do not have Desk permission to edit {doc.doctype} {doc.name}.",
            frappe.PermissionError,
        )


def is_usable_field(df):
    if df.fieldtype in ("Section Break", "Tab Break"):
        return True

    if not df.fieldname:
        return False

    if df.fieldname in SYSTEM_FIELDS:
        return False

    if df.fieldtype in SKIP_FIELD_TYPES:
        return False

    if getattr(df, "hidden", 0):
        return False

    # Do not skip read-only fields.
    # They may be used by depends_on / mandatory_depends_on / read_only_depends_on.
    # The frontend will render them disabled instead.
    if df.fieldtype in READ_ONLY_FIELD_TYPES:
        return False

    return True


def serialize_field(df, include_child_fields=True):
    fieldname = df.fieldname

    if not fieldname and df.fieldtype in ("Section Break", "Tab Break"):
        fieldname = f"layout_{getattr(df, 'idx', 0)}"

    label = df.label or ""

    if df.fieldtype not in ("Section Break", "Tab Break"):
        label = df.label or df.fieldname or df.fieldtype

    field = {
        "fieldname": fieldname,
        "label": label,
        "fieldtype": df.fieldtype,
        "options": df.options,
        "required": bool(getattr(df, "reqd", 0)),
        "default": df.default,
        "description": df.description,
        "depends_on": df.depends_on,
        "mandatory_depends_on": df.mandatory_depends_on,
        "read_only_depends_on": df.read_only_depends_on,
        "fetch_from": getattr(df, "fetch_from", None),
        "fetch_if_empty": bool(getattr(df, "fetch_if_empty", 0)),
        "precision": getattr(df, "precision", None),
        "length": getattr(df, "length", None),
        "idx": getattr(df, "idx", 0),
        "read_only": bool(getattr(df, "read_only", 0)),
    }

    if df.fieldtype == "Table" and df.options and include_child_fields:
        child_meta = frappe.get_meta(df.options)

        child_fields = []

        for child_df in child_meta.fields:
            if is_usable_field(child_df):
                child_fields.append(
                    serialize_field(
                        child_df,
                        include_child_fields=False,
                    )
                )

        field["child_doctype"] = df.options
        field["child_fields"] = child_fields

    return field


def get_mobile_fields_for_doctype(doctype):
    meta = frappe.get_meta(doctype)

    fields = []

    for df in meta.fields:
        if is_usable_field(df):
            fields.append(serialize_field(df))

    return fields


def get_schema_response(mobile_doctype, doctype):
    meta = frappe.get_meta(doctype)

    return {
        "mobile_doctype": mobile_doctype,
        "doctype": doctype,
        "title": meta.name,
        "title_field": meta.title_field,
        "fields": get_mobile_fields_for_doctype(doctype),
    }


def get_allowed_fieldnames(meta):
    allowed = set()

    for df in meta.fields:
        if is_usable_field(df) and df.fieldname:
            allowed.add(df.fieldname)

    return allowed


def clean_scalar_value(fieldtype, value):
    if value in ("", None):
        return None

    if fieldtype == "Check":
        if value in (True, "true", "True", "1", 1, "yes", "Yes"):
            return 1

        return 0

    if fieldtype == "Int":
        try:
            return int(value)
        except Exception:
            return 0

    if fieldtype in ("Float", "Currency", "Percent"):
        try:
            return float(value)
        except Exception:
            return 0

    return value


def normalise_loaded_value(df, value):
    if value is None:
        if df.fieldtype == "Check":
            return 0

        if df.fieldtype == "Table":
            return []

        return None

    if df.fieldtype == "Check":
        return 1 if value in (1, "1", True, "true", "True", "Yes", "yes") else 0

    if df.fieldtype == "Table":
        return value if isinstance(value, list) else []

    return value


def serialise_doc_for_mobile(doc, doctype):
    meta = frappe.get_meta(doctype)
    values = {}

    for df in meta.fields:
        fieldname = df.fieldname

        if not fieldname or not is_usable_field(df):
            continue

        if df.fieldtype == "Table":
            rows = []

            for row in doc.get(fieldname) or []:
                child_meta = frappe.get_meta(df.options)
                child_row = {}

                for child_df in child_meta.fields:
                    child_fieldname = child_df.fieldname

                    if not child_fieldname or not is_usable_field(child_df):
                        continue

                    child_row[child_fieldname] = normalise_loaded_value(
                        child_df,
                        row.get(child_fieldname),
                    )

                rows.append(child_row)

            values[fieldname] = rows
            continue

        values[fieldname] = normalise_loaded_value(df, doc.get(fieldname))

    return values


def get_existing_files_for_doc(doctype, docname):
    if not frappe.db.exists("DocType", "File"):
        return []

    if not frappe.has_permission("File", "read"):
        return []

    return frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": doctype,
            "attached_to_name": docname,
        },
        fields=[
            "name",
            "file_name",
            "file_url",
            "is_private",
            "file_size",
        ],
        order_by="creation desc",
    )


def set_doc_values_from_mobile(doc, values):
    meta = frappe.get_meta(doc.doctype)
    allowed_fields = get_allowed_fieldnames(meta)

    for df in meta.fields:
        fieldname = df.fieldname

        if not fieldname or fieldname not in allowed_fields:
            continue

        if fieldname not in values:
            continue

        value = values.get(fieldname)

        if df.fieldtype == "Table":
            if not isinstance(value, list):
                continue

            child_doctype = df.options
            child_meta = frappe.get_meta(child_doctype)
            child_allowed = get_allowed_fieldnames(child_meta)

            doc.set(fieldname, [])

            for row in value:
                if not isinstance(row, dict):
                    continue

                clean_row = {}

                for child_df in child_meta.fields:
                    child_fieldname = child_df.fieldname

                    if not child_fieldname or child_fieldname not in child_allowed:
                        continue

                    if child_fieldname not in row:
                        continue

                    clean_row[child_fieldname] = clean_scalar_value(
                        child_df.fieldtype,
                        row.get(child_fieldname),
                    )

                doc.append(fieldname, clean_row)

        else:
            doc.set(fieldname, clean_scalar_value(df.fieldtype, value))


def parse_time_to_datetime(time_value):
    if not time_value:
        return None

    time_text = str(time_value)

    if len(time_text.split(":")) == 2:
        time_text = f"{time_text}:00"

    return datetime.strptime(time_text, "%H:%M:%S")


def calculate_daily_timesheet_duration(values):
    start_time = values.get("start_time")
    end_time = values.get("end_time")

    if not start_time or not end_time:
        return None

    start = parse_time_to_datetime(start_time)
    end = parse_time_to_datetime(end_time)

    if not start or not end:
        return None

    if end < start:
        end = end + timedelta(days=1)

    return int((end - start).total_seconds())


def fetch_one_shift_assignment(full_name, filters, order_by=None):
    if not frappe.has_permission("Shift Assignment", "read"):
        return None

    rows = frappe.get_all(
        "Shift Assignment",
        fields=["name", "start_date", "end_date"],
        filters=[
            ["employee_name", "=", full_name],
            ["docstatus", "=", 1],
            *filters,
        ],
        order_by=order_by or "",
        limit_page_length=1,
    )

    return rows[0] if rows else None


def get_shift_allocation_for_date(full_name, date_value):
    if not date_value or not full_name:
        return None

    current = fetch_one_shift_assignment(
        full_name=full_name,
        filters=[
            ["start_date", "<=", date_value],
            ["end_date", ">=", date_value],
        ],
        order_by="start_date desc",
    )

    if current:
        return current.name

    previous = fetch_one_shift_assignment(
        full_name=full_name,
        filters=[
            ["end_date", "<", date_value],
        ],
        order_by="end_date desc",
    )

    next_shift = fetch_one_shift_assignment(
        full_name=full_name,
        filters=[
            ["start_date", ">", date_value],
        ],
        order_by="start_date asc",
    )

    chosen = None

    if previous and next_shift:
        current_date = getdate(date_value)
        previous_diff = abs((current_date - getdate(previous.end_date)).days)
        next_diff = abs((getdate(next_shift.start_date) - current_date).days)
        chosen = previous if previous_diff <= next_diff else next_shift
    else:
        chosen = previous or next_shift

    return chosen.name if chosen else None


def apply_shift_allocation_details_to_values(values, doctype):
    shift_allocation = values.get("shift_allocation")

    if not shift_allocation:
        return values

    if not frappe.has_permission("Shift Assignment", "read"):
        return values

    if not frappe.db.exists("Shift Assignment", shift_allocation):
        return values

    meta = frappe.get_meta(doctype)
    fieldnames = {df.fieldname for df in meta.fields if df.fieldname}

    shift_meta = frappe.get_meta("Shift Assignment")
    shift_fieldnames = {df.fieldname for df in shift_meta.fields if df.fieldname}

    shift_fields = [
        "name",
        "employee",
        "employee_name",
        "shift_type",
        "start_date",
        "end_date",
    ]

    for optional_field in [
        "custom_project",
        "custom_project_name",
        "custom_client",
        "custom_location",
        "custom_color",
        "custom_shift_type_color",
    ]:
        if optional_field in shift_fieldnames:
            shift_fields.append(optional_field)

    shift = frappe.db.get_value(
        "Shift Assignment",
        shift_allocation,
        shift_fields,
        as_dict=True,
    )

    if not shift:
        return values

    def set_field(possible_fieldnames, value):
        if value in (None, ""):
            return

        for fieldname in possible_fieldnames:
            if fieldname in fieldnames and not values.get(fieldname):
                values[fieldname] = value

    set_field(["employee"], shift.get("employee"))
    set_field(["employee_name"], shift.get("employee_name"))
    set_field(["shift_type"], shift.get("shift_type"))
    set_field(["shift_start_date", "start_date"], shift.get("start_date"))
    set_field(["shift_end_date", "end_date"], shift.get("end_date"))
    set_field(["custom_project", "project"], shift.get("custom_project"))
    set_field(["project_name", "custom_project_name"], shift.get("custom_project_name"))
    set_field(["client", "custom_client"], shift.get("custom_client"))
    set_field(["location", "custom_location"], shift.get("custom_location"))

    return values


def apply_daily_timesheet_defaults(values):
    full_name = get_user_full_name()

    if not values.get("current_user"):
        values["current_user"] = full_name

    if not values.get("date"):
        values["date"] = frappe.utils.today()

    duration = calculate_daily_timesheet_duration(values)

    if duration is not None:
        values["duration"] = duration

    if not values.get("shift_allocation"):
        shift_allocation = get_shift_allocation_for_date(
            full_name=values.get("current_user") or full_name,
            date_value=values.get("date"),
        )

        if shift_allocation:
            values["shift_allocation"] = shift_allocation

    values = apply_shift_allocation_details_to_values(values, "Daily Timesheet")

    return values


def mark_attendance_from_daily_timesheet(doc):
    if doc.doctype != "Daily Timesheet":
        return

    if not doc.get("date") or not doc.get("shift_allocation"):
        return

    if not frappe.has_permission("Attendance", "create"):
        return

    if not frappe.has_permission("Shift Assignment", "read"):
        return

    shift = frappe.get_doc("Shift Assignment", doc.shift_allocation)

    if not shift or not shift.get("employee"):
        return

    existing = frappe.get_all(
        "Attendance",
        filters={
            "employee": shift.employee,
            "attendance_date": doc.date,
        },
        fields=["name", "docstatus", "status"],
        limit_page_length=1,
    )

    if existing:
        existing_row = existing[0]

        if existing_row.docstatus == 0 and existing_row.status != "Present":
            attendance = frappe.get_doc("Attendance", existing_row.name)

            if attendance.has_permission("write"):
                attendance.status = "Present"
                attendance.save()

        return

    attendance = frappe.get_doc({
        "doctype": "Attendance",
        "employee": shift.employee,
        "employee_name": shift.employee_name,
        "attendance_date": doc.date,
        "status": "Present",
        "shift": shift.get("shift_type") or shift.get("shift"),
        "company": shift.get("company"),
    })

    attendance.insert()


def get_meta_field_map(doctype):
    meta = frappe.get_meta(doctype)
    return {df.fieldname: df for df in meta.fields if df.fieldname}


def resolve_fetch_from_value(parent_doctype, target_fieldname, values):
    parent_field_map = get_meta_field_map(parent_doctype)

    target_df = parent_field_map.get(target_fieldname)

    if not target_df:
        return None

    fetch_from = getattr(target_df, "fetch_from", None)

    if not fetch_from or "." not in fetch_from:
        return None

    source_fieldname, source_doc_fieldname = fetch_from.split(".", 1)
    source_df = parent_field_map.get(source_fieldname)

    if not source_df:
        return None

    if source_df.fieldtype not in ("Link", "Dynamic Link"):
        return None

    source_docname = values.get(source_fieldname)

    if not source_docname:
        return None

    if source_df.fieldtype == "Dynamic Link":
        linked_doctype = values.get(source_df.options)
    else:
        linked_doctype = source_df.options

    if not linked_doctype:
        return None

    if not frappe.has_permission(linked_doctype, "read"):
        frappe.throw(
            f"You do not have Desk permission to read {linked_doctype}.",
            frappe.PermissionError,
        )

    if not frappe.db.exists(linked_doctype, source_docname):
        return None

    return frappe.db.get_value(linked_doctype, source_docname, source_doc_fieldname)


@frappe.whitelist()
def get_form_schema(mobile_doctype, permission_type="create"):
    require_login()

    doctype = get_allowed_doctype(mobile_doctype)

    if permission_type not in ("create", "read", "write"):
        permission_type = "create"

    if permission_type == "write":
        if not frappe.has_permission(doctype, "write"):
            frappe.throw(
                f"You do not have Desk permission to edit {doctype}.",
                frappe.PermissionError,
            )
    else:
        require_desk_doctype_permission(doctype, permission_type)

    return get_schema_response(mobile_doctype, doctype)


@frappe.whitelist()
def get_mobile_doc_for_edit(mobile_doctype, docname):
    require_login()

    doctype = get_allowed_doctype(mobile_doctype)

    if not docname:
        frappe.throw("Document name is required.", frappe.ValidationError)

    if not frappe.db.exists(doctype, docname):
        frappe.throw(f"{doctype} {docname} was not found.", frappe.DoesNotExistError)

    doc = frappe.get_doc(doctype, docname)
    require_desk_doc_read(doc)

    return {
        "schema": get_schema_response(mobile_doctype, doctype),
        "doctype": doctype,
        "name": doc.name,
        "docstatus": doc.docstatus,
        "values": serialise_doc_for_mobile(doc, doctype),
        "files": get_existing_files_for_doc(doctype, docname),
        "can_write": has_desk_write_permission(doc),
    }

def build_mobile_doc_for_rules(doctype, values=None, docname=None):
    values = values or {}

    if docname and frappe.db.exists(doctype, docname):
        doc = frappe.get_doc(doctype, docname)
    else:
        doc = frappe.new_doc(doctype)

    set_doc_values_from_mobile(doc, values)

    return doc


@frappe.whitelist()
def update_mobile_doc(mobile_doctype, docname, values=None):
    require_login()

    doctype = get_allowed_doctype(mobile_doctype)

    if not docname:
        frappe.throw("Document name is required.", frappe.ValidationError)

    if not frappe.db.exists(doctype, docname):
        frappe.throw(f"{doctype} {docname} was not found.", frappe.DoesNotExistError)

    if isinstance(values, str):
        values = json.loads(values or "{}")

    values = values or {}

    doc = frappe.get_doc(doctype, docname)
    require_desk_doc_write(doc)

    if doctype == "Daily Timesheet":
        values = apply_daily_timesheet_defaults(values)

    set_doc_values_from_mobile(doc, values)

    doc.save()

    if doctype == "Daily Timesheet":
        mark_attendance_from_daily_timesheet(doc)

    return {
        "doctype": doc.doctype,
        "name": doc.name,
        "docstatus": doc.docstatus,
        "values": serialise_doc_for_mobile(doc, doctype),
        "files": get_existing_files_for_doc(doctype, doc.name),
    }


@frappe.whitelist()
def create_mobile_doc(mobile_doctype, values=None):
    require_login()

    doctype = get_allowed_doctype(mobile_doctype)

    if not frappe.has_permission(doctype, "create"):
        frappe.throw(
            f"You do not have Desk permission to create {doctype}.",
            frappe.PermissionError,
        )

    if isinstance(values, str):
        values = json.loads(values or "{}")

    values = values or {}

    meta = frappe.get_meta(doctype)

    if doctype == "Daily Timesheet":
        values = apply_daily_timesheet_defaults(values)

    doc = frappe.new_doc(doctype)
    set_doc_values_from_mobile(doc, values)

    fieldnames = {field.fieldname for field in meta.fields}

    if "owner_user" in fieldnames and not doc.get("owner_user"):
        doc.set("owner_user", frappe.session.user)

    if "created_by_user" in fieldnames and not doc.get("created_by_user"):
        doc.set("created_by_user", frappe.session.user)

    if "date_created" in fieldnames and not doc.get("date_created"):
        doc.set("date_created", now_datetime())

    doc.insert()

    if doctype == "Daily Timesheet":
        mark_attendance_from_daily_timesheet(doc)

    route = "/forms"

    if doctype == "Daily Timesheet":
        route = "/shifts"

    return {
        "doctype": doc.doctype,
        "name": doc.name,
        "route": route,
    }


@frappe.whitelist()
def get_prefill_values(
    mobile_doctype,
    date=None,
    project=None,
    link_task=None,
    work_order_number=None,
    project_scope_name=None,
    parent_task_name=None,
):
    require_login()

    doctype = get_allowed_doctype(mobile_doctype)

    if not frappe.has_permission(doctype, "create"):
        frappe.throw(
            f"You do not have Desk permission to create {doctype}.",
            frappe.PermissionError,
        )

    meta = frappe.get_meta(doctype)
    fieldnames = {df.fieldname for df in meta.fields if df.fieldname}

    values = {}

    def set_if_exists(possible_fieldnames, value):
        if value in (None, ""):
            return

        for fieldname in possible_fieldnames:
            if fieldname in fieldnames:
                values[fieldname] = value

    task = None
    project_doc = None

    if link_task and frappe.db.exists("Task", link_task) and frappe.has_permission("Task", "read"):
        task = frappe.db.get_value(
            "Task",
            link_task,
            [
                "name",
                "subject",
                "project",
                "parent_task_name",
                "parent_task",
                "project_scope_name",
                "work_order_number",
            ],
            as_dict=True,
        )

    if task:
        project = project or task.get("project")
        work_order_number = work_order_number or task.get("work_order_number")
        project_scope_name = project_scope_name or task.get("project_scope_name")

        # Work Summary should come from the linked Task itself.
        # Prefer Task.subject because that is the human-readable task name/title.
        # Fall back to Task.name if subject is empty.
        parent_task_name = (
            task.get("subject")
            or task.get("name")
            or parent_task_name
        )

    if project and frappe.db.exists("Project", project) and frappe.has_permission("Project", "read"):
        project_fields = ["name", "project_name"]

        project_meta = frappe.get_meta("Project")
        project_fieldnames = {df.fieldname for df in project_meta.fields}

        for optional_field in [
            "custom_project_location",
            "customer",
            "roster_or_shutdown",
        ]:
            if optional_field in project_fieldnames:
                project_fields.append(optional_field)

        project_doc = frappe.db.get_value(
            "Project",
            project,
            project_fields,
            as_dict=True,
        )

    set_if_exists(["project", "custom_project", "link_project"], project)

    if project_doc:
        readable_project_name = project_doc.get("project_name") or project_doc.get("name")

        set_if_exists(
            ["project_name", "custom_project_name", "project_title"],
            readable_project_name,
        )

        set_if_exists(
            ["project_location", "custom_project_location", "location"],
            project_doc.get("custom_project_location"),
        )

        set_if_exists(["customer", "client"], project_doc.get("customer"))

    set_if_exists(["link_task", "task", "task_name"], link_task)

    set_if_exists(
        [
            "work_summary",
            "parent_task_name",
            "work_scope",
            "scope_of_work",
            "custom_work_summary",
            "custom_work_scope",
        ],
        parent_task_name,
    )

    set_if_exists(
        [
            "work_area",
            "project_scope_name",
            "area",
            "scope_name",
            "custom_work_area",
            "custom_project_scope_name",
        ],
        project_scope_name,
    )

    set_if_exists(["work_order_number", "wo_number"], work_order_number)
    set_if_exists(["date", "attendance_date", "timesheet_date"], date)

    if doctype == "Daily Timesheet":
        daily_values = dict(values)

        if date:
            daily_values["date"] = date

        daily_values = apply_daily_timesheet_defaults(daily_values)

        for fieldname, value in daily_values.items():
            if fieldname in fieldnames:
                values[fieldname] = value

    return {
        "values": values
    }


@frappe.whitelist()
def search_link(doctype, txt="", page_length=20):
    require_login()

    if not doctype:
        frappe.throw("DocType is required")

    if not frappe.has_permission(doctype, "read"):
        frappe.throw(
            f"You do not have Desk permission to read {doctype}.",
            frappe.PermissionError,
        )

    return frappe.get_list(
        doctype,
        filters=[
            ["name", "like", f"%{txt}%"]
        ],
        fields=["name"],
        limit_page_length=int(page_length or 20),
        order_by="modified desc",
    )


@frappe.whitelist()
def apply_fetch_from(mobile_doctype, values=None, changed_fieldname=None, docname=None):
    require_login()

    doctype = get_allowed_doctype(mobile_doctype)

    if docname:
        if not frappe.db.exists(doctype, docname):
            frappe.throw(f"{doctype} {docname} was not found.", frappe.DoesNotExistError)

        doc = frappe.get_doc(doctype, docname)
        require_desk_doc_write(doc)
    else:
        if not (
            frappe.has_permission(doctype, "create")
            or frappe.has_permission(doctype, "write")
        ):
            frappe.throw(
                f"You do not have Desk permission to use {doctype}.",
                frappe.PermissionError,
            )

    if isinstance(values, str):
        values = json.loads(values or "{}")

    values = values or {}

    meta = frappe.get_meta(doctype)
    updated_values = {}

    for df in meta.fields:
        if not is_usable_field(df):
            continue

        if df.fieldtype == "Table":
            continue

        fieldname = df.fieldname
        fetch_from = getattr(df, "fetch_from", None)

        if not fetch_from:
            continue

        if changed_fieldname and "." in fetch_from:
            source_fieldname = fetch_from.split(".", 1)[0]

            if source_fieldname != changed_fieldname:
                continue

        fetch_if_empty = bool(getattr(df, "fetch_if_empty", 0))

        if fetch_if_empty and values.get(fieldname):
            continue

        fetched_value = resolve_fetch_from_value(doctype, fieldname, values)

        if fetched_value is not None:
            updated_values[fieldname] = fetched_value

    return {
        "values": updated_values
    }


@frappe.whitelist()
def run_field_change(mobile_doctype, changed_fieldname, values=None, docname=None):
    require_login()

    doctype = get_allowed_doctype(mobile_doctype)

    if docname:
        if not frappe.db.exists(doctype, docname):
            frappe.throw(f"{doctype} {docname} was not found.", frappe.DoesNotExistError)

        doc = frappe.get_doc(doctype, docname)
        require_desk_doc_write(doc)
    else:
        if not (
            frappe.has_permission(doctype, "create")
            or frappe.has_permission(doctype, "write")
        ):
            frappe.throw(
                f"You do not have Desk permission to use {doctype}.",
                frappe.PermissionError,
            )

    if isinstance(values, str):
        values = json.loads(values or "{}")

    values = values or {}

    if doctype == "Daily Timesheet":
        updates = {}
        warnings = []

        if not values.get("current_user"):
            updates["current_user"] = get_user_full_name()
            values["current_user"] = updates["current_user"]

        if not values.get("date"):
            updates["date"] = today()
            values["date"] = updates["date"]

        if changed_fieldname in ("start_time", "end_time"):
            duration = calculate_daily_timesheet_duration(values)

            if duration is not None:
                updates["duration"] = duration
                values["duration"] = duration

        if changed_fieldname in ("date", "current_user", "shift_allocation"):
            current_user = values.get("current_user") or get_user_full_name()
            date_value = values.get("date")

            if current_user and date_value and not values.get("shift_allocation"):
                shift_allocation = get_shift_allocation_for_date(
                    full_name=current_user,
                    date_value=date_value,
                )

                if shift_allocation:
                    updates["shift_allocation"] = shift_allocation
                    values["shift_allocation"] = shift_allocation

                    values = apply_shift_allocation_details_to_values(values, "Daily Timesheet")

                    for fieldname, value in values.items():
                        if fieldname not in updates and value not in (None, ""):
                            updates[fieldname] = value
                else:
                    warnings.append("No allocated shifts found, including nearest. Please contact the office.")

        if updates or warnings:
            return {
                "values": updates,
                "messages": [],
                "warnings": warnings,
            }

    doc = build_mobile_doc_for_rules(
        doctype=doctype,
        values=values,
        docname=docname,
    )

    if hasattr(doc, "mobile_field_change"):
        result = doc.mobile_field_change(changed_fieldname=changed_fieldname) or {}

        return {
            "values": result.get("values", {}),
            "messages": result.get("messages", []),
            "warnings": result.get("warnings", []),
        }

    from verto.api.mobile.field_change_handlers import handle_mobile_field_change

    result = handle_mobile_field_change(
        doctype=doctype,
        mobile_doctype=mobile_doctype,
        changed_fieldname=changed_fieldname,
        values=values,
        user=frappe.session.user,
    )

    if not result:
        result = {}

    return {
        "values": result.get("values", {}),
        "messages": result.get("messages", []),
        "warnings": result.get("warnings", []),
    }