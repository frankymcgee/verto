import frappe
from frappe import _
from frappe.utils import cint, now_datetime
from frappe.utils.file_manager import save_file


TASK_DOCTYPE = "Task"
CHECKLIST_FIELD_CANDIDATES = (
    "checklist",
    "task_checklist",
    "custom_checklist",
)
ITEM_FIELD_CANDIDATES = (
    "checklist_item",
    "item",
    "description",
    "label",
    "subject",
)
COMPLETED_FIELD_CANDIDATES = (
    "completed",
    "is_completed",
    "checked",
    "done",
)
COMPLETED_BY_FIELD_CANDIDATES = (
    "completed_by",
    "checked_by",
)
COMPLETED_ON_FIELD_CANDIDATES = (
    "completed_on",
    "checked_on",
)
EVIDENCE_FILE_EXTENSIONS = {
    ".csv",
    ".doc",
    ".docx",
    ".gif",
    ".heic",
    ".heif",
    ".jpeg",
    ".jpg",
    ".ods",
    ".odt",
    ".pdf",
    ".png",
    ".txt",
    ".webp",
    ".xls",
    ".xlsx",
}


def require_login():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)


def first_existing_field(fieldnames, candidates):
    return next((fieldname for fieldname in candidates if fieldname in fieldnames), None)


def get_checklist_config():
    cached = getattr(frappe.local, "verto_task_checklist_config", None)

    if cached is not None:
        return cached or None

    task_meta = frappe.get_meta(TASK_DOCTYPE)
    table_field = None

    for fieldname in CHECKLIST_FIELD_CANDIDATES:
        candidate = task_meta.get_field(fieldname)

        if candidate and candidate.fieldtype == "Table" and candidate.options:
            table_field = candidate
            break

    if not table_field or not frappe.db.exists("DocType", table_field.options):
        frappe.local.verto_task_checklist_config = {}
        return None

    child_meta = frappe.get_meta(table_field.options)
    child_fieldnames = {df.fieldname for df in child_meta.fields}
    item_field = first_existing_field(child_fieldnames, ITEM_FIELD_CANDIDATES)
    completed_field = first_existing_field(child_fieldnames, COMPLETED_FIELD_CANDIDATES)

    if not item_field or not completed_field:
        frappe.local.verto_task_checklist_config = {}
        return None

    config = {
        "table_field": table_field.fieldname,
        "child_doctype": table_field.options,
        "item_field": item_field,
        "completed_field": completed_field,
        "completed_by_field": first_existing_field(
            child_fieldnames,
            COMPLETED_BY_FIELD_CANDIDATES,
        ),
        "completed_on_field": first_existing_field(
            child_fieldnames,
            COMPLETED_ON_FIELD_CANDIDATES,
        ),
    }
    frappe.local.verto_task_checklist_config = config
    return config


def parse_completed(value):
    if isinstance(value, bool):
        return cint(value)

    normalised = str(value).strip().lower()

    if normalised in {"1", "true", "yes", "on"}:
        return 1

    if normalised in {"0", "false", "no", "off"}:
        return 0

    frappe.throw(_("Completed must be true or false."), frappe.ValidationError)


def get_evidence_upload():
    files = getattr(frappe.request, "files", None) or {}
    upload = files.get("evidence_file") or files.get("file")

    if not upload:
        frappe.throw(
            _("Upload evidence before completing this checklist item."),
            frappe.ValidationError,
        )

    filename = (upload.filename or "").strip()
    extension = f".{filename.rsplit('.', 1)[-1].lower()}" if "." in filename else ""

    if not filename or extension not in EVIDENCE_FILE_EXTENSIONS:
        frappe.throw(
            _(
                "Evidence must be an image, PDF, Microsoft Office document, "
                "text file, or CSV."
            ),
            frappe.ValidationError,
        )

    content = upload.stream.read()

    if not content:
        frappe.throw(_("The evidence file is empty."), frappe.ValidationError)

    return filename, content


def save_checklist_evidence(task):
    filename, content = get_evidence_upload()

    return save_file(
        filename,
        content,
        TASK_DOCTYPE,
        task.name,
        is_private=1,
    )


def calculate_progress(rows, completed_field):
    if not rows:
        return None

    completed_count = sum(cint(row.get(completed_field)) for row in rows)
    return round((completed_count / len(rows)) * 100, 2)


def sync_task_checklist_progress(doc, method=None):
    """Keep Task.progress aligned when a checklist is saved from Desk or mobile."""
    config = get_checklist_config()

    if not config or doc.doctype != TASK_DOCTYPE:
        return

    rows = doc.get(config["table_field"]) or []
    progress = calculate_progress(rows, config["completed_field"])

    # Tasks without a checklist keep their existing/manual progress behaviour.
    if progress is not None:
        doc.progress = progress


def serialise_checklist_row(row, config):
    completed_by_field = config.get("completed_by_field")
    completed_on_field = config.get("completed_on_field")

    return {
        "name": row.get("name"),
        "description": row.get(config["item_field"]) or "",
        "completed": cint(row.get(config["completed_field"])),
        "completed_by": row.get(completed_by_field) if completed_by_field else None,
        "completed_on": row.get(completed_on_field) if completed_on_field else None,
    }


def attach_checklists_to_tasks(tasks):
    config = get_checklist_config()

    for task in tasks:
        task["checklist"] = []

    if not config or not tasks:
        return tasks

    task_names = [task.get("name") for task in tasks if task.get("name")]

    if not task_names:
        return tasks

    fields = [
        "name",
        "parent",
        "idx",
        config["item_field"],
        config["completed_field"],
    ]

    for optional_field in (
        config.get("completed_by_field"),
        config.get("completed_on_field"),
    ):
        if optional_field and optional_field not in fields:
            fields.append(optional_field)

    rows = frappe.get_all(
        config["child_doctype"],
        filters={
            "parent": ["in", task_names],
            "parenttype": TASK_DOCTYPE,
            "parentfield": config["table_field"],
        },
        fields=fields,
        order_by="parent asc, idx asc",
        limit_page_length=5000,
    )

    rows_by_task = {}

    for row in rows:
        rows_by_task.setdefault(row.parent, []).append(
            serialise_checklist_row(row, config)
        )

    for task in tasks:
        task["checklist"] = rows_by_task.get(task.get("name"), [])

    return tasks


def get_parent_progress(task):
    if not task.parent_task:
        return None

    return frappe.db.get_value(TASK_DOCTYPE, task.parent_task, "progress")


def has_open_task_assignment(task_name, user):
    assignments = frappe.get_all(
        "ToDo",
        filters={
            "reference_type": TASK_DOCTYPE,
            "reference_name": task_name,
            "allocated_to": user,
            "status": ["not in", ["Cancelled", "Closed"]],
        },
        pluck="name",
        limit_page_length=1,
    )
    return bool(assignments)


def can_update_checklist(task):
    has_write_permission = frappe.has_permission(
        TASK_DOCTYPE,
        ptype="write",
        doc=task,
        user=frappe.session.user,
    )

    return has_write_permission or has_open_task_assignment(
        task.name,
        frappe.session.user,
    )


@frappe.whitelist(methods=["POST"])
def set_checklist_item_completed(task_name, item_name, completed):
    require_login()

    if not task_name or not item_name:
        frappe.throw(_("Task and checklist item are required."), frappe.ValidationError)

    config = get_checklist_config()

    if not config:
        frappe.throw(_("The Task checklist is not configured."), frappe.ValidationError)

    task = frappe.get_doc(TASK_DOCTYPE, task_name)

    if not can_update_checklist(task):
        frappe.throw(_("You are not assigned to this Task."), frappe.PermissionError)

    # Serialise simultaneous checklist updates for the same Task so the final
    # percentage always includes every user's latest tick.
    frappe.db.sql(
        "select name from `tabTask` where name = %s for update",
        task_name,
    )
    task.reload()

    # Recheck after acquiring the lock in case the assignment was removed by
    # another request while this one was waiting.
    if not can_update_checklist(task):
        frappe.throw(_("You are not assigned to this Task."), frappe.PermissionError)

    row = next(
        (
            checklist_row
            for checklist_row in (task.get(config["table_field"]) or [])
            if checklist_row.name == item_name
        ),
        None,
    )

    if not row:
        frappe.throw(_("Checklist item does not belong to this Task."), frappe.PermissionError)

    completed_value = parse_completed(completed)
    was_completed = cint(row.get(config["completed_field"]))
    evidence_file = None

    # Evidence is mandatory every time an incomplete item is completed. The
    # File is attached to the Task and is deliberately never removed when the
    # checklist item is later unchecked, preserving the audit trail.
    if completed_value and not was_completed:
        evidence_file = save_checklist_evidence(task)

    row.set(config["completed_field"], completed_value)

    completed_by_field = config.get("completed_by_field")
    completed_on_field = config.get("completed_on_field")

    if completed_by_field:
        row.set(completed_by_field, frappe.session.user if completed_value else None)

    if completed_on_field:
        row.set(completed_on_field, now_datetime() if completed_value else None)

    sync_task_checklist_progress(task)
    task.save(ignore_permissions=True)

    rows = task.get(config["table_field"]) or []
    completed_count = sum(cint(item.get(config["completed_field"])) for item in rows)

    return {
        "task": task.name,
        "item": serialise_checklist_row(row, config),
        "checklist": [serialise_checklist_row(item, config) for item in rows],
        "completed_count": completed_count,
        "total_count": len(rows),
        "progress": task.progress,
        "parent_task": task.parent_task,
        "parent_progress": get_parent_progress(task),
        "evidence": (
            {
                "name": evidence_file.name,
                "file_name": evidence_file.file_name,
                "file_url": evidence_file.file_url,
                "is_private": cint(evidence_file.is_private),
            }
            if evidence_file
            else None
        ),
    }
