import frappe
from frappe import _

from verto.api.mobile.voice_jha_permissions import user_can_access_work_summary


SETTINGS_DOCTYPE = "Verto Mobile Settings"
JHA_DOCTYPE = "Digital Job Hazard Analysis"
ACTIVE_JHA_STATUSES = (
    "Draft",
    "Voice Discussion in Progress",
    "Incomplete - Actions Required",
    "Ready for Team Review",
)


def _require_login():
    if frappe.session.user == "Guest":
        frappe.throw(_("Login required"), frappe.PermissionError)


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


def _validate_work_summary(work_summary: str):
    if not work_summary or not frappe.db.exists("Task", work_summary):
        frappe.throw(_("Work Summary was not found."), frappe.DoesNotExistError)

    task = frappe.get_doc("Task", work_summary)
    if task.get("type") != "Work Summary":
        frappe.throw(_("The selected Task is not a Work Summary."), frappe.ValidationError)
    if not task.has_permission("read"):
        frappe.throw(_("You cannot access this Work Summary."), frappe.PermissionError)
    if not user_can_access_work_summary(task.name):
        frappe.throw(_("This Work Summary is not assigned to you."), frappe.PermissionError)

    return task


def _get_active_jha_name(work_summary: str) -> str:
    return (
        frappe.db.get_value(
            JHA_DOCTYPE,
            {
                "work_summary": work_summary,
                "jha_status": ["in", list(ACTIVE_JHA_STATUSES)],
            },
            "name",
            order_by="modified desc",
        )
        or ""
    )


def _row_dict(row, fields):
    return {field: row.get(field) for field in fields}


def _serialize_jha(doc):
    return {
        "name": doc.name,
        "status": doc.jha_status,
        "revision": doc.revision,
        "project": doc.project,
        "work_summary": doc.work_summary,
        "work_summary_title": doc.work_summary_title,
        "work_order_number": doc.work_order_number,
        "work_area": doc.work_area,
        "ai_bot": doc.ai_bot,
        "source_revision": doc.source_revision,
        "modified": doc.modified,
        "work_steps": [
            _row_dict(
                row,
                (
                    "name",
                    "idx",
                    "sequence",
                    "activity",
                    "step_origin",
                    "source_step_identifier",
                    "hold_or_pause_point",
                ),
            )
            for row in (doc.work_steps or [])
        ],
        "hazards_and_controls": [
            _row_dict(
                row,
                (
                    "name",
                    "idx",
                    "work_step_sequence",
                    "work_step_reference",
                    "hazard_or_energy_source",
                    "people_exposed",
                    "credible_consequence",
                    "existing_controls",
                    "additional_controls",
                    "hierarchy_level",
                    "control_owner",
                    "verification_method",
                    "verification_status",
                    "critical_risk",
                    "critical_control",
                    "permit_or_ccv_required",
                    "initial_risk",
                    "residual_risk",
                    "information_source",
                ),
            )
            for row in (doc.hazards_and_controls or [])
        ],
        "participants": [
            _row_dict(
                row,
                (
                    "name",
                    "idx",
                    "employee",
                    "participant_name",
                    "role",
                    "present_for_discussion",
                    "transcription_consent",
                    "acknowledged",
                    "acknowledged_at",
                ),
            )
            for row in (doc.participants or [])
        ],
    }


def _get_jha_doc(jha_name: str):
    if not jha_name or not frappe.db.exists(JHA_DOCTYPE, jha_name):
        frappe.throw(_("Digital JHA was not found."), frappe.DoesNotExistError)

    doc = frappe.get_doc(JHA_DOCTYPE, jha_name)
    if not doc.has_permission("read"):
        frappe.throw(_("You cannot access this Digital JHA."), frappe.PermissionError)

    return doc


@frappe.whitelist(methods=["GET"])
def get_voice_jha_bootstrap(work_summary: str):
    """Return trusted Work Summary context and any active JHA draft.

    This endpoint deliberately does not submit, approve, sign or authorise work.
    """
    _require_login()
    task = _validate_work_summary(work_summary)

    existing_name = _get_active_jha_name(task.name)
    existing_jha = None
    if existing_name:
        existing_jha = _serialize_jha(_get_jha_doc(existing_name))

    return {
        "work_summary": task.name,
        "title": task.subject,
        "project": task.project,
        "work_area": task.get("parent_task_name") or "",
        "work_order_number": task.get("work_order_number") or "",
        "description": task.get("description") or "",
        "peri_bot": _get_peri_bot(),
        "existing_jha": existing_jha,
        "realtime_enabled": False,
        "prototype_stage": "mobile-draft-workflow",
        "notice": "PERI can prepare a draft JHA only. Human review and sign-on remain mandatory before work proceeds.",
    }


@frappe.whitelist(methods=["GET"])
def get_voice_jha_snapshot(jha_name: str):
    _require_login()
    return _serialize_jha(_get_jha_doc(jha_name))


@frappe.whitelist(methods=["POST"])
def create_voice_jha_draft(work_summary: str):
    _require_login()
    task = _validate_work_summary(work_summary)

    existing = _get_active_jha_name(task.name)
    if existing:
        result = _serialize_jha(_get_jha_doc(existing))
        result["created"] = False
        return result

    doc = frappe.get_doc(
        {
            "doctype": JHA_DOCTYPE,
            "project": task.project,
            "work_summary": task.name,
            "work_summary_title": task.subject,
            "work_order_number": task.get("work_order_number") or "",
            "work_area": task.get("parent_task_name") or "",
            "jha_status": "Draft",
            "ai_bot": _get_peri_bot() or None,
        }
    )

    if not doc.has_permission("create"):
        frappe.throw(_("You cannot create a Digital JHA for this Work Summary."), frappe.PermissionError)

    doc.insert()

    result = _serialize_jha(doc)
    result["created"] = True
    return result
