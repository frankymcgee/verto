import frappe
from frappe import _
from frappe.utils import cint


SETTINGS_DOCTYPE = "Verto Mobile Settings"


def _require_login():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)


def _assigned_to_current_user(task) -> bool:
    assigned = str(task.get("_assign") or "")
    return frappe.session.user in assigned


def _get_peri_bot():
    try:
        settings = frappe.get_cached_doc(SETTINGS_DOCTYPE)
    except Exception:
        return ""

    for fieldname in ("peri_bot_name", "ai_photo_analysis_bot"):
        if settings.meta.has_field(fieldname):
            value = str(settings.get(fieldname) or "").strip()
            if value and frappe.db.exists("Raven Bot", value):
                return value
    return ""


@frappe.whitelist(methods=["GET"])
def get_voice_jha_bootstrap(work_summary: str):
    """Return the minimum trusted context needed to start a voice-JHA draft.

    This endpoint deliberately does not create, submit, approve or sign a JHA.
    """
    _require_login()

    if not work_summary or not frappe.db.exists("Task", work_summary):
        frappe.throw(_("Work Summary was not found."), frappe.DoesNotExistError)

    task = frappe.get_doc("Task", work_summary)
    if task.get("type") != "Work Summary":
        frappe.throw(_("The selected Task is not a Work Summary."), frappe.ValidationError)
    if not task.has_permission("read"):
        frappe.throw(_("You cannot access this Work Summary."), frappe.PermissionError)
    if not _assigned_to_current_user(task) and "System Manager" not in frappe.get_roles():
        frappe.throw(_("This Work Summary is not assigned to you."), frappe.PermissionError)

    return {
        "work_summary": task.name,
        "title": task.subject,
        "project": task.project,
        "work_area": task.get("parent_task_name") or "",
        "work_order_number": task.get("work_order_number") or "",
        "description": task.get("description") or "",
        "peri_bot": _get_peri_bot(),
        "realtime_enabled": False,
        "prototype_stage": "data-model-and-session-shell",
        "notice": "Voice discussion is not connected yet. Human review and sign-on remain mandatory.",
    }


@frappe.whitelist(methods=["POST"])
def create_voice_jha_draft(work_summary: str):
    _require_login()
    context = get_voice_jha_bootstrap(work_summary)

    if not frappe.has_permission("Digital Job Hazard Analysis", "create"):
        frappe.throw(_("You cannot create a Digital JHA."), frappe.PermissionError)

    existing = frappe.db.get_value(
        "Digital Job Hazard Analysis",
        {"work_summary": work_summary, "jha_status": ["in", ["Draft", "Voice Discussion in Progress"]]},
        "name",
    )
    if existing:
        return {"name": existing, "created": False}

    doc = frappe.get_doc({
        "doctype": "Digital Job Hazard Analysis",
        "project": context["project"],
        "work_summary": work_summary,
        "work_summary_title": context["title"],
        "work_order_number": context["work_order_number"],
        "work_area": context["work_area"],
        "jha_status": "Draft",
        "ai_bot": context["peri_bot"] or None,
    })
    doc.insert()
    return {"name": doc.name, "created": True}
